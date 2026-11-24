const LEVELS = {
  urgent: { label: "Urgent – today", cls: "urgent" },
  gp: { label: "Routine GP appointment", cls: "gp" },
  self_care: { label: "Self-care", cls: "self" },
};

export default function TriageCard({ level, headline, reason, advice, symptom, severity, duration, fever }) {
  const lv = LEVELS[level] || { label: level, cls: "gp" };
  return (
    <article className={`card triage ${lv.cls}`} aria-label="Triage result">
      <div className="card-tag">Triage result · {lv.label}</div>
      <h2>{headline}</h2>
      <p className="why"><strong>Why:</strong> {reason}.</p>
      <dl>
        <div><dt>Symptom</dt><dd>{symptom}</dd></div>
        <div><dt>Severity</dt><dd>{severity ? `${severity}/10` : "n/a"}</dd></div>
        <div><dt>Duration</dt><dd>{duration || "n/a"}</dd></div>
        <div><dt>Fever</dt><dd>{fever === true ? "yes" : fever === false ? "no" : "n/a"}</dd></div>
      </dl>
      <p className="advice">{advice}</p>
      <p className="note">General guidance, not a diagnosis.</p>
    </article>
  );
}
