export default function MessageBubble({ from, text }) {
  return (
    <div className={`bubble-row ${from}`}>
      <div className={`bubble ${from}`}>
        {text.split("\n").map((line, i) => <p key={i}>{line}</p>)}
      </div>
    </div>
  );
}
