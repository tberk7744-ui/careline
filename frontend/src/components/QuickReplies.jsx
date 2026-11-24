// Turns the `buttons` list of a Rasa reply into clickable quick replies.
export default function QuickReplies({ buttons, onSelect, disabled }) {
  return (
    <div className="quick-replies" role="group" aria-label="Quick replies">
      {buttons.map((b) => (
        <button key={b.payload} type="button" disabled={disabled} onClick={() => onSelect(b)}>
          {b.title}
        </button>
      ))}
    </div>
  );
}
