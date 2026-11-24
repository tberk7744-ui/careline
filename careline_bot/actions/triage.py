"""Deterministic triage rules for the CareLine prototype.

IMPORTANT: this rule base is an illustrative prototype for an academic assignment. It has NOT been
clinically validated and must not be used for real patients. In a deployed system the thresholds and
advice texts would be authored and signed off by clinicians and linked to an approved content source.

Design choice: the triage decision is made by transparent rules, not by a learned model. The language
model only has to understand *what the patient said* (NLU); the safety-critical decision is explainable,
testable and auditable, and the reason for every outcome can be shown to the patient and the nurse.
"""
import re
from dataclasses import dataclass
from typing import Optional

# Safety net independent of the intent classifier: if any of these appear anywhere in the patient's
# own words, the outcome is "emergency" even when NLU misclassified the message.
RED_FLAG_PATTERNS = [
    r"chest (pain|pressure|tight)", r"heart attack", r"stroke", r"can'?t breathe", r"cannot breathe",
    r"(struggling|difficulty|trouble|hard) (to breathe|breathing)", r"short(ness)? of breath",
    r"not breathing", r"unconscious", r"collapsed", r"faint(ed)? and", r"seizure", r"overdose",
    r"(heavy|heavily|severe|a lot of) bleed", r"bleeding (heavily|a lot)", r"coughing up blood",
    r"face (is )?droop", r"lips? (are |is )?(turning )?blue", r"severe allergic", r"anaphyla",
    r"throat is swelling", r"suicid", r"kill myself", r"\bemergency\b", r"ambulance",
    r"too many (tablets|pills)", r"can'?t move", r"chok(e|ing)", r"slurred", r"pass(ed|ing)? out",
]
_RED_FLAG_RE = re.compile("|".join(RED_FLAG_PATTERNS), re.IGNORECASE)

# Symptoms for which the form adaptively asks the extra fever question
INFECTION_SYMPTOMS = ("cough", "sore throat", "cold", "runny nose", "earache", "fever",
                      "urinary pain", "diarrhoea", "vomiting")

SELF_CARE_ADVICE = {
    "cough": "Rest, drink plenty of fluids and avoid smoke. A pharmacist can advise on cough remedies.",
    "sore throat": "Drink plenty of fluids and rest. A pharmacist can advise on lozenges or pain relief.",
    "cold": "Rest, keep warm and drink plenty of fluids. A pharmacist can advise on symptom relief.",
    "runny nose": "Rest and drink plenty of fluids. A pharmacist can advise on symptom relief.",
    "headache": "Rest, drink water and avoid screens for a while. A pharmacist can advise on pain relief.",
    "back pain": "Keep gently active rather than resting in bed. A pharmacist can advise on pain relief.",
    "diarrhoea": "Drink plenty of fluids in small sips. A pharmacist can advise on rehydration.",
    "vomiting": "Take small, frequent sips of fluid. A pharmacist can advise on rehydration.",
    "nausea": "Take small sips of fluid and eat small, plain meals.",
}
DEFAULT_ADVICE = "Rest and look after yourself at home for now. A pharmacist can advise on symptom relief."
SAFETY_NET = ("Contact the clinic if it is not improving after a few days, if it gets worse, or if "
              "you are worried. Call 112 / 999 if you develop any emergency symptoms.")

_WORD_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "nine": 9, "ten": 10, "couple": 2, "few": 3, "several": 5}


def has_red_flag(text: Optional[str]) -> bool:
    return bool(text) and bool(_RED_FLAG_RE.search(text))


def parse_severity(text: Optional[str]) -> Optional[int]:
    """First whole number between 1 and 10 found in the answer ('about a 7', '7/10', button payload)."""
    for token in re.findall(r"\d+", text or ""):
        if 1 <= int(token) <= 10:
            return int(token)
    return None


def parse_duration_days(text: Optional[str]) -> Optional[float]:
    """Convert a free-text duration ('3 days', 'two weeks', 'since yesterday') to days."""
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in ("today", "this morning", "tonight", "last night", "hour")):
        return 0.5
    if "yesterday" in t:
        return 1.0
    match = re.search(r"(\d+(?:\.\d+)?|\b(?:%s)\b)\s*(?:of\s+)?(day|week|month|year)" % "|".join(_WORD_NUMBERS), t)
    if not match:
        return None
    raw, unit = match.groups()
    number = _WORD_NUMBERS[raw] if raw in _WORD_NUMBERS else float(raw)
    return number * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]


@dataclass
class TriageResult:
    level: str      # emergency | urgent | gp | self_care
    reason: str     # shown to the patient and the nurse (explainability)
    advice: str


def triage(symptom: str, red_flag: bool, severity: Optional[int], duration_days: Optional[float],
           fever: Optional[bool], free_text: str = "") -> TriageResult:
    """Rules are evaluated from most to least urgent; the first match wins. When information is
    missing or ambiguous the rule base escalates (errs towards the safer, more urgent outcome)."""
    symptom = (symptom or "").lower()

    if red_flag or has_red_flag(symptom) or has_red_flag(free_text):
        return TriageResult("emergency", "an emergency warning sign was reported",
                            "Call 112 / 999 now or go to the nearest emergency department.")
    if severity is None:
        return TriageResult("gp", "the severity could not be established, so a clinician should assess it",
                            "I can show you the next available appointments.")
    if severity >= 8:
        return TriageResult("urgent", f"you rated the severity {severity}/10",
                            "I can offer you a same-day appointment.")
    if fever and duration_days is not None and duration_days >= 3:
        return TriageResult("urgent", "a high temperature has lasted 3 days or more",
                            "I can offer you a same-day appointment.")
    if severity >= 5:
        return TriageResult("gp", f"you rated the severity {severity}/10",
                            "I can show you the next available appointments.")
    if duration_days is None:
        return TriageResult("gp", "the duration could not be established, so a clinician should assess it",
                            "I can show you the next available appointments.")
    if duration_days > 7:
        return TriageResult("gp", "the symptom has lasted more than a week",
                            "I can show you the next available appointments.")
    advice = next((text for key, text in SELF_CARE_ADVICE.items() if key in symptom), DEFAULT_ADVICE)
    return TriageResult("self_care", f"mild symptoms ({severity}/10) for a short time",
                        f"{advice} {SAFETY_NET}")
