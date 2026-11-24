// Sends one patient message to the Rasa REST channel and returns the bot's replies.
const WEBHOOK = "/webhooks/rest/webhook";

export async function sendMessage(sender, message) {
  const res = await fetch(WEBHOOK, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sender, message }),
  });
  if (!res.ok) throw new Error(`Rasa returned HTTP ${res.status}`);
  return res.json(); // [{ text, buttons } | { custom: { type, ... } }]
}

// Random, non-identifying session id (no personal data is sent to the bot).
export function newSessionId() {
  return "web-" + crypto.getRandomValues(new Uint32Array(2)).join("");
}
