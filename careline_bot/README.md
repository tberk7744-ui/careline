# CareLine - healthcare triage and appointment-scheduling chatbot (Rasa)

Academic prototype. The triage rules are illustrative and not clinically validated.

## Requirements
Python 3.8-3.10 (Rasa Open Source 3.6 does not support newer versions).

```bash
python3.10 -m venv .venv && source .venv/bin/activate
pip install rasa==3.6.21 rasa-sdk==3.6.2
```

## Train and test
```bash
rasa data validate
rasa train --fixed-model-name careline
rasa test nlu --nlu data/nlu.yml --cross-validation --folds 5 --out results/nlu
rasa test core --stories tests/test_stories.yml --out results/core
```

## Run (two terminals, both from this folder)
`endpoints.yml` points to the Docker service `actions`; for a local run use `endpoints.local.yml`.
```bash
rasa run actions --port 5055
rasa run --enable-api --cors "*" --port 5005 -m models/careline.tar.gz --endpoints endpoints.local.yml
```
Send a message:
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
     -H "Content-Type: application/json" -d '{"sender": "demo", "message": "hello"}'
```

## Layout
| Path | Content |
|---|---|
| `config.yml` | NLU pipeline (DIET) and dialogue policies (Rule, Memoization, TED) |
| `domain.yml` | intents, entities, slots, triage form, responses with quick-reply buttons |
| `data/` | NLU examples, rules, stories |
| `actions/triage.py` | triage rule base and red-flag patterns |
| `actions/ehr.py` | mock EHR / booking system (SQLite, created on first start as `clinic.db`) |
| `actions/actions.py` | form validation, triage, booking, cancellation, nurse handover |
| `components/red_flag_guard.py` | rule-based emergency override in the NLU pipeline |
| `tests/test_stories.yml` | end-to-end test conversations |
