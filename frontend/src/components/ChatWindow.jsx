import { useEffect, useRef, useState } from "react";
import { newSessionId, sendMessage } from "../api.js";
import MessageBubble from "./MessageBubble.jsx";
import QuickReplies from "./QuickReplies.jsx";
import TriageCard from "./TriageCard.jsx";
import AppointmentCard from "./AppointmentCard.jsx";
import { EmergencyBanner, HandoverBanner } from "./Banners.jsx";

const CUSTOM = {
  triage_card: TriageCard,
  appointment_card: AppointmentCard,
  emergency_banner: EmergencyBanner,
  handover_banner: HandoverBanner,
};

export default function ChatWindow() {
  const [sender] = useState(newSessionId);
  const [items, setItems] = useState([]);       // {from:"user"|"bot", text?, buttons?, custom?}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);
  const started = useRef(false);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [items, busy]);

  async function send(message, label = message, silent = false) {
    if (!message.trim() || busy) return;
    setError(null);
    if (!silent) setItems((xs) => [...xs, { from: "user", text: label }]);
    setBusy(true);
    try {
      const replies = await sendMessage(sender, message);
      setItems((xs) => [...xs, ...replies.map((r) => ({ from: "bot", ...r }))]);
    } catch (e) {
      setError("CareLine is not reachable right now. Please try again, or call the clinic.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!started.current) { started.current = true; send("/greet", "", true); }
  }, []);

  // only the newest bot message keeps clickable quick replies
  const lastButtons = items.reduce((idx, it, i) => (it.buttons?.length ? i : idx), -1);
  const lastUser = items.reduce((idx, it, i) => (it.from === "user" ? i : idx), -1);

  return (
    <section className="chat" aria-label="CareLine chat">
      <header className="chat-header">
        <div className="logo" aria-hidden="true">+</div>
        <div>
          <h1>CareLine</h1>
          <p>Clinic triage &amp; appointments</p>
        </div>
      </header>

      <div className="chat-log" role="log" aria-live="polite">
        {items.map((it, i) => {
          if (it.custom) {
            const { ref: bookingRef, ...data } = it.custom;   // "ref" is reserved by React
            const Card = CUSTOM[data.type];
            return Card ? <Card key={i} bookingRef={bookingRef} {...data} /> : null;
          }
          return (
            <div key={i}>
              {it.text && <MessageBubble from={it.from} text={it.text} />}
              {it.buttons?.length > 0 && (
                <QuickReplies buttons={it.buttons} disabled={busy || i !== lastButtons || lastUser > i}
                              onSelect={(b) => send(b.payload, b.title)} />
              )}
            </div>
          );
        })}
        {busy && <div className="typing" aria-label="CareLine is typing"><span /><span /><span /></div>}
        {error && <div className="error" role="alert">{error}</div>}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); setInput(""); }}>
        <label htmlFor="msg" className="sr-only">Your message</label>
        <input id="msg" value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Type a message…" autoComplete="off" />
        <button type="submit" disabled={busy || !input.trim()}>Send</button>
      </form>
    </section>
  );
}
