import ChatWindow from "./components/ChatWindow.jsx";

export default function App() {
  return (
    <div className="page">
      <ChatWindow />
      <p className="disclaimer">
        Academic prototype. CareLine does not give a diagnosis. In an emergency call 112 (EU) or 999 (UK).
      </p>
    </div>
  );
}
