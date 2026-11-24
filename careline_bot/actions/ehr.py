"""Mock EHR / booking back-end for the CareLine prototype.

A SQLite file stands in for the clinic's EHR/booking API so the prototype can be run and tested
end-to-end. Every function below maps one-to-one to a REST call of a real system (the FHIR resource
that would be used is named in each docstring), so replacing this module is the only change needed
to integrate with a production EHR.

Privacy by design: no name, date of birth or contact detail is stored. A patient is identified by a
salted SHA-256 hash of the channel's sender id (pseudonymisation, GDPR Art. 4(5)).
"""
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

DB_PATH = os.environ.get("CLINIC_DB", "clinic.db")
_SALT = os.environ.get("PATIENT_TOKEN_SALT", "dev-only-salt-change-in-production")

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointment_slots (
    id INTEGER PRIMARY KEY, start_iso TEXT NOT NULL, clinician TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('same_day', 'routine')), booked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS appointments (
    ref TEXT PRIMARY KEY, slot_id INTEGER NOT NULL REFERENCES appointment_slots(id),
    patient_token TEXT NOT NULL, reason TEXT, triage_level TEXT,
    status TEXT NOT NULL DEFAULT 'booked', created_iso TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handover_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_iso TEXT NOT NULL, patient_token TEXT NOT NULL,
    priority TEXT NOT NULL, context_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting');
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_iso TEXT NOT NULL, patient_token TEXT NOT NULL,
    event TEXT NOT NULL, detail TEXT);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def patient_token(sender_id: str) -> str:
    """Pseudonymous patient identifier derived from the channel sender id."""
    return hashlib.sha256((_SALT + sender_id).encode()).hexdigest()[:16]


def init_db() -> None:
    """Create the tables and seed demo slots for the next five working days (idempotent)."""
    with _connect() as con:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM appointment_slots").fetchone()[0]:
            return
        day, added = datetime.now().replace(minute=0, second=0, microsecond=0), 0
        clinicians = ["Dr Hale (GP)", "Dr Osei (GP)", "Nurse Marin"]
        while added < 5:
            day += timedelta(days=1)
            if day.weekday() >= 5:            # skip Saturday/Sunday
                continue
            for i, (hour, minute) in enumerate([(9, 0), (9, 40), (11, 20), (14, 0), (15, 40), (16, 20)]):
                start = day.replace(hour=hour, minute=minute)
                kind = "same_day" if added == 0 else "routine"   # first working day = urgent capacity
                con.execute("INSERT INTO appointment_slots (start_iso, clinician, kind) VALUES (?,?,?)",
                            (start.isoformat(timespec="minutes"), clinicians[i % 3], kind))
            added += 1


def audit(sender_id: str, event: str, detail: str = "") -> None:
    """Append-only audit trail (accountability; HIPAA audit controls, 45 CFR 164.312(b))."""
    with _connect() as con:
        con.execute("INSERT INTO audit_log (created_iso, patient_token, event, detail) VALUES (?,?,?,?)",
                    (_now(), patient_token(sender_id), event, detail))


def free_slots(urgent: bool, limit: int = 4) -> List[Dict]:
    """FHIR: GET /Slot?status=free. Urgent cases are offered the earliest (same-day) capacity first;
    routine cases are only offered routine slots so urgent capacity is protected."""
    where = "booked = 0" if urgent else "booked = 0 AND kind = 'routine'"
    with _connect() as con:
        rows = con.execute(f"SELECT * FROM appointment_slots WHERE {where} ORDER BY start_iso LIMIT ?",
                           (limit,)).fetchall()
    return [dict(r) for r in rows]


def book(sender_id: str, slot_id: int, reason: str, triage_level: str) -> Optional[Dict]:
    """FHIR: POST /Appointment. Atomic: the UPDATE only succeeds if the slot is still free,
    so two patients can never be given the same slot."""
    with _connect() as con:
        cur = con.execute("UPDATE appointment_slots SET booked = 1 WHERE id = ? AND booked = 0", (slot_id,))
        if cur.rowcount == 0:
            return None
        ref = "APT-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        con.execute("INSERT INTO appointments (ref, slot_id, patient_token, reason, triage_level, created_iso)"
                    " VALUES (?,?,?,?,?,?)",
                    (ref, slot_id, patient_token(sender_id), reason, triage_level, _now()))
        slot = dict(con.execute("SELECT * FROM appointment_slots WHERE id = ?", (slot_id,)).fetchone())
    audit(sender_id, "appointment_booked", ref)
    return {"ref": ref, **slot}


def cancel(sender_id: str, ref: str) -> Optional[Dict]:
    """FHIR: PATCH /Appointment/{id} status=cancelled. Only the patient who made the booking can
    cancel it; an unknown reference and someone else's reference give the same answer, so
    references cannot be probed."""
    with _connect() as con:
        row = con.execute(
            "SELECT a.ref, a.slot_id, s.start_iso, s.clinician FROM appointments a"
            " JOIN appointment_slots s ON s.id = a.slot_id"
            " WHERE a.ref = ? AND a.patient_token = ? AND a.status = 'booked'",
            (ref, patient_token(sender_id))).fetchone()
        if row is None:
            return None
        con.execute("UPDATE appointments SET status = 'cancelled' WHERE ref = ?", (ref,))
        con.execute("UPDATE appointment_slots SET booked = 0 WHERE id = ?", (row["slot_id"],))
    audit(sender_id, "appointment_cancelled", ref)
    return dict(row)


def enqueue_handover(sender_id: str, priority: str, context: Dict) -> str:
    """Put the conversation into the nurse queue together with its full context."""
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO handover_queue (created_iso, patient_token, priority, context_json) VALUES (?,?,?,?)",
            (_now(), patient_token(sender_id), priority, json.dumps(context)))
        handover_id = cur.lastrowid
    audit(sender_id, "handover_requested", f"HND-{handover_id:04d} priority={priority}")
    return f"HND-{handover_id:04d}"


init_db()
