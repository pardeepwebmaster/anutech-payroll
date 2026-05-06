import { useEffect, useRef, useState } from "react";
import api from "../../lib/api";

const SUGGESTIONS = [
  "Show me pending leave requests",
  "What's the next PF deadline?",
  "Detect anomalies in last month's payroll",
  "Total monthly salary spend by department",
];

export default function AIChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const message = text ?? input;
    if (!message.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    try {
      const { data } = await api.post("/ai-chat", { message });
      setMessages((m) => [
        ...m,
        { role: "assistant", agent: data.agent, content: data.text, usage: data.usage, cached: data.cached },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", error: err?.response?.data?.detail || "Request failed" },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 h-[calc(100vh-8rem)] flex flex-col">
      <div>
        <h1 className="text-2xl font-semibold">AI Assistant</h1>
        <p className="text-sm text-gray-500 mt-1">
          Powered by Claude. Routes your question to HR / payroll / finance / compliance.
        </p>
      </div>

      <div ref={scrollRef} className="card flex-1 overflow-y-auto space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12 space-y-3">
            <div className="text-gray-500">Try a question:</div>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="btn-secondary text-xs" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-2xl rounded-2xl px-4 py-3 ${
              m.role === "user"
                ? "bg-primary-500 text-white"
                : m.error
                ? "bg-red-50 border border-red-200 text-red-700"
                : "bg-primary-50 text-gray-900"
            }`}>
              {m.role === "assistant" && m.agent && (
                <div className="text-xs uppercase tracking-wider text-primary-700 mb-1 font-medium">
                  {m.agent}{m.cached ? " · cached" : ""}
                </div>
              )}
              <div className="whitespace-pre-wrap text-sm">{m.error ?? m.content}</div>
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="bg-primary-50 rounded-2xl px-4 py-3 text-sm text-gray-500">
              Thinking...
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="flex gap-2"
      >
        <input
          className="input flex-1"
          placeholder="Ask anything about your payroll, employees, or compliance..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button type="submit" className="btn-primary" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
