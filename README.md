# CareLine – healthcare triage and appointment-scheduling chatbot (Rasa + React)

Academic prototype (BSBI, *Advanced Conversational UI Design and Chatbot Development*).
The triage rules are illustrative and **not clinically validated**.

| Path | Content |
|---|---|
| `careline_bot/` | Rasa Open Source 3.6 project (NLU, rules, stories, custom actions, mock EHR) |
| `frontend/` | React (Vite) chat UI: quick replies, triage card, appointment card, emergency and nurse-handover banners |
| `docker/` | Dockerfiles for `rasa`, `actions` and `web` (nginx) and the nginx config |
| `docker-compose.yml` | the three services and the persistent `clinic-data` volume |
| `deploy/README.md` | step-by-step cloud deployment (Google Cloud Compute Engine VM) |

## Run everything with Docker Compose
```bash
cp .env.example .env            # then set PATIENT_TOKEN_SALT (openssl rand -hex 32)
docker compose up -d --build    # the Rasa model is trained while the image is built
docker compose ps
```
Open http://localhost – nginx serves the React UI and proxies `/webhooks/` to Rasa.
Ports 5005 and 5055 are not published.

```bash
curl -X POST http://localhost/webhooks/rest/webhook \
     -H "Content-Type: application/json" -d '{"sender": "demo", "message": "hello"}'
```

## Local development without Docker
See `careline_bot/README.md` for the Rasa side. The front-end:
```bash
cd frontend && npm install && npm run dev   # http://localhost:5173, proxies /webhooks to :5005
```

## Custom payloads used by the UI
The actions send, next to the normal text and buttons, a `custom` message that the UI renders:
`triage_card`, `appointment_card`, `emergency_banner`, `handover_banner`.
