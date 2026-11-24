"""Re-runs the 30 end-to-end scenarios of the test report against the Docker Compose stack,
through nginx (http://localhost/webhooks/rest/webhook), and records per-turn latency.

usage: python run_scenarios.py [BASE_URL]   (default http://localhost)
"""
import json
import statistics
import sys
import time
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost").rstrip("/")
URL = BASE + "/webhooks/rest/webhook"
LAT = []


def say(sender, msg):
    req = urllib.request.Request(URL, json.dumps({"sender": sender, "message": msg}).encode(),
                                 {"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    LAT.append((time.perf_counter() - t) * 1000)
    return out


def text(replies):
    return " ".join(r.get("text", "") for r in replies)


def customs(replies):
    return [r["custom"]["type"] for r in replies if isinstance(r.get("custom"), dict)]


def buttons(replies):
    return [b for r in replies for b in r.get("buttons", [])]


def sid():
    return "e2e-" + uuid.uuid4().hex[:10]


def consented(s):
    say(s, "Hello")
    return say(s, "/give_consent")


def start_triage(s, symptom):
    consented(s)
    return say(s, symptom)


RESULTS = []


def check(num, cat, desc, ok, got):
    RESULTS.append((num, cat, desc, bool(ok), got))
    print(f"{'PASS' if ok else 'FAIL'} {num:5} {cat:14} {desc} -> {got[:110]}")


# ---------------- round 1: each custom action ----------------
s = sid()
r1 = start_triage(s, "I have a sore throat")
r2 = say(s, "/deny")
r3 = say(s, "/affirm")
r4 = say(s, '/inform{"duration":"2 days"}')
order_ok = ("ANY of these" in text(r1) and "temperature" in text(r2)
            and "How long" in text(r3) and "how bad" in text(r4))
check("1.1", "Aksiyon", "validate_triage_form: question order", order_ok, "red flag -> fever -> duration -> severity")
r = say(s, '/inform{"severity":"5"}')
check("1.2", "Aksiyon", "action_triage: GP + triage_card",
      "routine GP appointment" in text(r) and "triage_card" in customs(r), text(r)[:80] + f" {customs(r)}")
r = say(s, "/book_appointment")
slots = [b for b in buttons(r) if b["payload"].startswith("/select_slot")]
check("1.3", "Aksiyon", "action_show_slots: slots as buttons", len(slots) > 0, f"{len(slots)} slots")
r = say(s, slots[0]["payload"])
ref = next((x["custom"]["ref"] for x in r if isinstance(x.get("custom"), dict)
            and x["custom"]["type"] == "appointment_card"), None)
check("1.4", "Aksiyon", "action_book_appointment: booking + appointment_card",
      "is booked" in text(r) and ref, f"ref={ref}")
say(s, "/cancel_appointment")
r = say(s, ref)
check("1.5", "Aksiyon", "action_cancel_appointment: real ref", "has been cancelled" in text(r), text(r))
say(s, "/cancel_appointment")
r = say(s, "APT-XXXXXX")
check("1.6", "Aksiyon", "action_cancel_appointment: fake ref", "couldn't find" in text(r), text(r))
s = sid(); consented(s)
r = say(s, "/request_human")
check("1.7", "Aksiyon", "action_handover: normal + handover_banner",
      "passing you to a nurse" in text(r) and "handover_banner" in customs(r), text(r)[:70] + f" {customs(r)}")
s = sid(); consented(s)
r = say(s, "I have crushing chest pain")
check("1.8", "Aksiyon", "action_handover (emergency) + emergency_banner",
      "may be an emergency" in text(r) and "emergency_banner" in customs(r), text(r)[:70] + f" {customs(r)}")

# ---------------- round 2 ----------------
s = sid(); say(s, "Hello"); say(s, "/deny_consent")
r = say(s, "I have a sore throat")
check("2.1", "Onay", "no consent -> triage blocked", "need your consent" in text(r), text(r))
s = sid(); say(s, "Hello"); say(s, "/deny_consent")
r = say(s, "/book_appointment")
check("2.2", "Onay", "no consent -> no slots", "need your consent" in text(r), text(r))

s = sid(); start_triage(s, "I have a sore throat")
r = say(s, "/affirm")
check("2.3", "Triyaj", "red flag yes -> emergency + handover", "may be an emergency" in text(r), text(r)[:90])

s = sid(); start_triage(s, "I have a headache")
r = say(s, "/deny")
no_fever = "temperature" not in text(r) and "How long" in text(r)
say(s, '/inform{"duration":"2 days"}')
r = say(s, '/inform{"severity":"2"}')
check("2.4", "Triyaj", "headache 2d sev2 -> self_care, no fever Q",
      no_fever and "managed at home" in text(r), text(r)[:90])

s = sid(); start_triage(s, "I have a headache"); say(s, "/deny"); say(s, '/inform{"duration":"2 days"}')
r = say(s, '/inform{"severity":"8"}')
check("2.5", "Triyaj", "headache 2d sev8 -> urgent", "seen today" in text(r), text(r)[:90])
r = say(s, "/book_appointment")
check("2.7", "Randevu", "urgent -> same-day slots", "today's urgent slots" in text(r), text(r))

s = sid(); start_triage(s, "I have a sore throat"); say(s, "/deny"); say(s, "/affirm")
say(s, '/inform{"duration":"5 days"}')
r = say(s, '/inform{"severity":"5"}')
check("2.6", "Triyaj", "fever >= 3 days -> urgent", "3 days or more" in text(r), text(r)[:90])

s = sid(); start_triage(s, "I have a headache"); say(s, "/deny"); say(s, '/inform{"duration":"2 days"}')
r = say(s, "15")
check("2.8", "Doğrulama", "severity 15 rejected", "number from 1 to 10" in text(r), text(r))

s = sid(); start_triage(s, "I have a headache")
r = say(s, "/stop")
check("2.9", "Form kesintisi", "/stop in form", "I've stopped" in text(r), text(r))
s = sid(); start_triage(s, "I have a headache")
r = say(s, "/request_human")
check("2.10", "Form kesintisi", "/request_human in form", "passing you to a nurse" in text(r), text(r)[:80])
s = sid(); start_triage(s, "I have a headache")
r = say(s, "I have crushing chest pain")
check("2.11", "Form kesintisi", "chest pain in form -> emergency", "may be an emergency" in text(r), text(r)[:80])
s = sid(); start_triage(s, "I have a headache")
r = say(s, "/ask_privacy")
check("2.12", "Form kesintisi", "privacy in form, form resumes",
      "pseudonymous" in text(r) and "ANY of these" in text(r), text(r)[:80])

s = sid(); consented(s)
r = say(s, "/book_appointment")
check("2.13", "Randevu", "booking without triage -> normal slots", "next available" in text(r), text(r))
r = say(s, '/select_slot{"slot_id":"abc"}')
check("2.14", "Doğrulama", "slot_id abc rejected", "no longer available" in text(r), text(r)[:80])
s = sid(); say(s, "Hello"); say(s, "/deny_consent")
r = say(s, '/select_slot{"slot_id":"9"}')
check("2.15", "Onay", "no consent -> no booking", "need your consent" in text(r), text(r))
s = sid()
r = say(s, "merhaba")
check("2.16", "NLU", "Turkish 'merhaba' -> fallback", "didn't understand" in text(r), text(r))

a, b = sid(), sid(); consented(a); consented(b)
ra = say(a, "/book_appointment"); say(b, "/book_appointment")
pay = [x for x in buttons(ra) if x["payload"].startswith("/select_slot")][-1]["payload"]
ra = say(a, pay); rb = say(b, pay)
aref = next((x["custom"]["ref"] for x in ra if isinstance(x.get("custom"), dict)
             and x["custom"]["type"] == "appointment_card"), None)
check("2.17", "Çok kullanıcı", "A and B pick the same slot",
      aref and "no longer available" in text(rb), f"A={aref}; B={text(rb)[:50]}")
say(b, "/cancel_appointment")
r = say(b, aref)
check("2.18", "Güvenlik", "B cancels with A's ref -> refused", "couldn't find" in text(r), text(r)[:70])
say(a, "/cancel_appointment")
r = say(a, aref.lower())
check("2.19", "Doğrulama", "A cancels with lowercase ref", "has been cancelled" in text(r), text(r)[:70])
s = sid()
r = say(s, "are you a bot?")
check("2.20", "NLU", "bot challenge", "automated assistant" in text(r), text(r)[:70])
s = sid(); start_triage(s, "I have a headache"); say(s, "/deny"); say(s, '/inform{"duration":"10 days"}')
r = say(s, '/inform{"severity":"2"}')
check("2.21", "Triyaj", "10 days -> gp", "more than a week" in text(r), text(r)[:90])
s = sid(); start_triage(s, "I have a headache"); say(s, "/deny"); say(s, "for a while")
r = say(s, '/inform{"severity":"2"}')
check("2.22", "Triyaj", "unclear duration -> gp", "could not be established" in text(r), text(r)[:90])

passed = sum(1 for x in RESULTS if x[3])
lat = sorted(LAT)
p95 = lat[max(0, int(round(0.95 * len(lat))) - 1)]
summary = {"base": BASE, "passed": passed, "total": len(RESULTS), "turns": len(lat),
           "median_ms": round(statistics.median(lat)), "p95_ms": round(p95), "max_ms": round(lat[-1]),
           "under_3s": sum(1 for x in lat if x < 3000)}
print(json.dumps(summary, ensure_ascii=False))
json.dump({"summary": summary, "results": RESULTS}, open("e2e_results.json", "w"), ensure_ascii=False, indent=1)
