export function EmergencyBanner({ reference }) {
  return (
    <div className="banner emergency" role="alert">
      <strong>⚠ Possible emergency – call 112 / 999 now</strong>
      <span>Do not wait for an appointment and do not drive yourself.
        {reference && <> The clinic nurse has been alerted (ref {reference}).</>}</span>
    </div>
  );
}

export function HandoverBanner({ reference, priority }) {
  return (
    <div className="banner handover" role="status">
      <strong>👩‍⚕️ Connecting you to a nurse</strong>
      <span>Reference {reference}{priority === "high" ? " · high priority" : ""}. They can see this
        conversation, so you won't need to repeat anything.</span>
    </div>
  );
}
