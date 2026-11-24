"""Custom actions of the CareLine triage and appointment assistant (run with `rasa run actions`)."""
from datetime import datetime
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from . import ehr
from .triage import INFECTION_SYMPTOMS, has_red_flag, parse_duration_days, parse_severity, triage

TRIAGE_SLOTS = ["symptom", "red_flag", "fever", "duration", "severity"]
NURSE_BUTTON = {"title": "Speak to a nurse", "payload": "/request_human"}
BOOK_BUTTON = {"title": "Book an appointment", "payload": "/book_appointment"}
DONE_BUTTON = {"title": "I'm done", "payload": "/goodbye"}


def _fmt(start_iso: Text) -> Text:
    return datetime.fromisoformat(start_iso).strftime("%a %d %b, %H:%M")


def _user_texts(tracker: Tracker) -> List[Text]:
    """Everything the patient typed in this session (button payloads excluded)."""
    texts = [e.get("text") or "" for e in tracker.events if e.get("event") == "user"]
    return [t for t in texts if t and not t.startswith("/")]


class ValidateTriageForm(FormValidationAction):
    """Validates each answer and adapts the question list to what the patient has said so far."""

    def name(self) -> Text:
        return "validate_triage_form"

    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher,
                             tracker: Tracker, domain: DomainDict) -> List[Text]:
        # Adaptive questioning:
        # 1) a reported red flag ends the questioning immediately - no further questions are asked
        if tracker.get_slot("red_flag") is True:
            return ["symptom", "red_flag"]
        # 2) the temperature question is only asked for infection-type symptoms
        symptom = (tracker.get_slot("symptom") or "").lower()
        ask_fever = any(key in symptom for key in INFECTION_SYMPTOMS) and "fever" not in symptom
        return [slot for slot in domain_slots if slot != "fever" or ask_fever]

    def validate_symptom(self, slot_value: Any, dispatcher: CollectingDispatcher,
                         tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        # Prefer the extracted entity ("sore throat") over the whole sentence ("I have a sore throat")
        entity = next(tracker.get_latest_entity_values("symptom"), None)
        value = (entity or str(slot_value or "")).strip()
        if len(value) < 3 or value.startswith("/"):
            dispatcher.utter_message(text="Please describe the symptom in a few words, for example 'sore throat'.")
            return {"symptom": None}
        if has_red_flag(value) or has_red_flag(tracker.latest_message.get("text")):
            return {"symptom": value, "red_flag": True}      # keyword safety net
        return {"symptom": value}

    def validate_severity(self, slot_value: Any, dispatcher: CollectingDispatcher,
                          tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        score = parse_severity(str(slot_value))
        if score is None:
            dispatcher.utter_message(text="I need a number from 1 to 10.")
            return {"severity": None}
        return {"severity": str(score)}

    def validate_duration(self, slot_value: Any, dispatcher: CollectingDispatcher,
                          tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        value = str(slot_value or "").strip()
        if has_red_flag(value):
            return {"duration": value, "red_flag": True}
        # An unparseable duration is kept: the triage rules then escalate instead of guessing.
        return {"duration": value or None}


class ActionTriage(Action):
    """Applies the triage rule base to the collected answers and explains the outcome."""

    def name(self) -> Text:
        return "action_triage"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:
        symptom = tracker.get_slot("symptom") or "unspecified symptom"
        severity = parse_severity(tracker.get_slot("severity"))
        duration = tracker.get_slot("duration")
        fever = tracker.get_slot("fever")
        if fever is None and any(word in symptom.lower() for word in ("fever", "temperature")):
            fever = True                      # the reported symptom itself is a high temperature
        result = triage(symptom, tracker.get_slot("red_flag") is True, severity,
                        parse_duration_days(duration), fever, " ".join(_user_texts(tracker)))

        summary = (f"symptom={symptom}; severity={f'{severity}/10' if severity else 'n/a'}; "
                   f"duration={duration or 'n/a'}; fever={fever if fever is not None else 'n/a'}; "
                   f"outcome={result.level} ({result.reason})")
        ehr.audit(tracker.sender_id, "triage_completed", summary)

        if result.level == "emergency":
            reference = ehr.enqueue_handover(tracker.sender_id, "emergency", {"triage": summary})
            dispatcher.utter_message(response="utter_emergency")
            dispatcher.utter_message(text=f"I have also alerted the clinic nurse (reference {reference}).")
            # custom payload: the React front-end draws a red emergency banner from it
            dispatcher.utter_message(json_message={"type": "emergency_banner", "reference": reference,
                                                   "reason": result.reason})
        else:
            headline = {"urgent": "You should be seen today",
                        "gp": "A routine GP appointment is recommended",
                        "self_care": "This can usually be managed at home"}[result.level]
            buttons = [NURSE_BUTTON, DONE_BUTTON] if result.level == "self_care" else [BOOK_BUTTON, NURSE_BUTTON]
            dispatcher.utter_message(
                text=(f"{headline}, because {result.reason}. {result.advice}\n\n"
                      "This is general guidance, not a diagnosis."),
                buttons=buttons)
            # custom payload: the React front-end renders it as a triage result card
            dispatcher.utter_message(json_message={
                "type": "triage_card", "level": result.level, "headline": headline,
                "reason": result.reason, "advice": result.advice, "symptom": symptom,
                "severity": severity, "duration": duration, "fever": fever})

        # keep the outcome for booking/handover, clear the answers so a new triage starts clean
        return ([SlotSet("triage_level", result.level), SlotSet("triage_summary", summary)]
                + [SlotSet(slot, None) for slot in TRIAGE_SLOTS])


class ActionShowSlots(Action):
    """Reads free appointment slots from the booking system and offers them as quick replies."""

    def name(self) -> Text:
        return "action_show_slots"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:
        urgent = tracker.get_slot("triage_level") == "urgent"
        slots = ehr.free_slots(urgent=urgent)
        if not slots:
            dispatcher.utter_message(text="There are no free appointments online at the moment.",
                                     buttons=[NURSE_BUTTON])
            return []
        intro = ("These are the earliest appointments, including today's urgent slots:" if urgent
                 else "These are the next available appointments:")
        buttons = [{"title": f"{_fmt(s['start_iso'])} - {s['clinician']}",
                    "payload": f'/select_slot{{"slot_id":"{s["id"]}"}}'} for s in slots]
        dispatcher.utter_message(text=intro, buttons=buttons)
        return []


class ActionBookAppointment(Action):
    """Books the chosen slot in the booking system and returns a booking reference."""

    def name(self) -> Text:
        return "action_book_appointment"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:
        if not tracker.get_slot("consent"):
            dispatcher.utter_message(response="utter_ask_consent")
            return [SlotSet("slot_id", None)]
        raw = str(tracker.get_slot("slot_id") or "")
        booking = None
        if raw.isdigit():
            booking = ehr.book(tracker.sender_id, int(raw),
                               reason=tracker.get_slot("triage_summary") or "booked without triage",
                               triage_level=tracker.get_slot("triage_level") or "not_triaged")
        if booking is None:
            dispatcher.utter_message(text="Sorry, that appointment is no longer available. Please choose another.",
                                     buttons=[BOOK_BUTTON])
            return [SlotSet("slot_id", None)]
        dispatcher.utter_message(
            text=(f"Your appointment is booked: {_fmt(booking['start_iso'])} with {booking['clinician']}.\n"
                  f"Booking reference: {booking['ref']} - keep it, you need it to cancel or change the appointment.\n"
                  "If you get worse before then, contact the clinic, or call 112 / 999 in an emergency."),
            buttons=[DONE_BUTTON])
        # custom payload: the React front-end renders it as an appointment confirmation card
        dispatcher.utter_message(json_message={
            "type": "appointment_card", "ref": booking["ref"], "start": _fmt(booking["start_iso"]),
            "start_iso": booking["start_iso"], "clinician": booking["clinician"],
            "triage_level": tracker.get_slot("triage_level") or "not_triaged"})
        return [SlotSet("slot_id", None)]


class ActionCancelAppointment(Action):
    """Cancels an appointment by reference and frees the slot; offers re-booking (= reschedule)."""

    def name(self) -> Text:
        return "action_cancel_appointment"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:
        ref = str(tracker.get_slot("booking_ref") or "").upper().strip()
        cancelled = ehr.cancel(tracker.sender_id, ref) if ref else None
        if cancelled is None:
            dispatcher.utter_message(
                text="I couldn't find an active appointment with that reference for you. "
                     "Please check the reference, or speak to a nurse.",
                buttons=[NURSE_BUTTON])
        else:
            dispatcher.utter_message(
                text=f"Your appointment on {_fmt(cancelled['start_iso'])} with {cancelled['clinician']} "
                     f"({cancelled['ref']}) has been cancelled. Would you like a new one?",
                buttons=[{"title": "Book a new appointment", "payload": "/book_appointment"}, DONE_BUTTON])
        return [SlotSet("booking_ref", None)]


class ActionHandover(Action):
    """Hands the conversation to a nurse together with its context, so the patient does not have to
    repeat anything. In production this would also open the live-agent channel and pause the bot."""

    def name(self) -> Text:
        return "action_handover"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:
        texts = _user_texts(tracker)
        # Note: an emergency handover is recorded even without consent - protecting the patient's
        # vital interests is its own lawful basis (GDPR Art. 6(1)(d) and 9(2)(c)).
        emergency = (tracker.get_intent_of_latest_message() == "emergency"
                     or tracker.get_slot("triage_level") == "emergency"
                     or tracker.get_slot("red_flag") is True
                     or any(has_red_flag(t) for t in texts))
        priority = "emergency" if emergency else ("high" if tracker.get_slot("triage_level") == "urgent" else "normal")
        context = {
            "triage_summary": tracker.get_slot("triage_summary"),
            "triage_level": tracker.get_slot("triage_level"),
            "answers_in_progress": {s: tracker.get_slot(s) for s in TRIAGE_SLOTS
                                    if tracker.get_slot(s) is not None},
            "last_patient_messages": texts[-6:],
        }
        reference = ehr.enqueue_handover(tracker.sender_id, priority, context)
        if emergency:
            dispatcher.utter_message(
                text=f"I have alerted the clinic nurse as an emergency (reference {reference}). "
                     "Do not wait for them - call 112 / 999 now.")
        else:
            dispatcher.utter_message(
                text=f"I'm passing you to a nurse now (reference {reference}). They can see what you "
                     "have told me, so you won't need to repeat it. Please stay in this chat.")
        # custom payload: the React front-end shows an emergency banner or a nurse-handover strip
        dispatcher.utter_message(json_message={
            "type": "emergency_banner" if emergency else "handover_banner",
            "reference": reference, "priority": priority})
        return [SlotSet(slot, None) for slot in TRIAGE_SLOTS]
