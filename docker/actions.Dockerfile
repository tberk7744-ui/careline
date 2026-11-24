# Action server: custom actions (triage, booking, handover) and the mock EHR (SQLite on a volume).
FROM rasa/rasa-sdk:3.6.2
WORKDIR /app
COPY careline_bot/actions/ /app/actions/
COPY careline_bot/components/ /app/components/
USER root
RUN mkdir -p /data && chown 1001:0 /data
USER 1001
EXPOSE 5055
CMD ["start", "--actions", "actions", "--port", "5055"]
