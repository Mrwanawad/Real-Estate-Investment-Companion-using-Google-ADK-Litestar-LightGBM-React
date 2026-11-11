import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { createSession, streamMessage, type ApiLanguage, type Artifact, type StreamEvent } from "../api";
import { ArtifactView, CitationList } from "./Artifacts";
import { Markdown } from "./markdown";

interface Msg {
  id: number;
  role: "user" | "assistant";
  text: string;
  artifacts: Artifact[];
  tool?: string | null;
}

const KNOWN_TOOLS = [
  "search_units",
  "compare_financing",
  "project_returns",
  "assess_risks",
  "search_knowledge",
  "create_lead",
  "build_report",
];

export default function ChatPage() {
  const { t, i18n } = useTranslation();
  const apiLang: ApiLanguage = (i18n.resolvedLanguage ?? "en").startsWith("ar") ? "ar" : "en";
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<Promise<string> | null>(null);
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  // App remounts this page (key=language), so each language gets a fresh session.
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || streaming) return;
      setInput("");
      setError(null);
      setStreaming(true);
      const assistantId = nextId.current + 1;
      nextId.current += 2;
      setMessages((m) => [
        ...m,
        { id: assistantId - 1, role: "user", text: message, artifacts: [] },
        { id: assistantId, role: "assistant", text: "", artifacts: [] },
      ]);
      const patch = (fn: (m: Msg) => Msg) =>
        setMessages((all) => all.map((m) => (m.id === assistantId ? fn(m) : m)));
      const onEvent = (e: StreamEvent) => {
        if (e.type === "tool") patch((m) => ({ ...m, tool: e.status === "started" ? e.name : null }));
        else if (e.type === "delta") patch((m) => ({ ...m, text: m.text + e.text }));
        else if (e.type === "artifact") patch((m) => ({ ...m, artifacts: [...m.artifacts, e.artifact] }));
        else if (e.type === "error") setError(e.message || t("chat.error"));
        else patch((m) => ({ ...m, tool: null }));
      };
      try {
        sessionRef.current ??= createSession(apiLang);
        const id = await sessionRef.current;
        await streamMessage(id, message, apiLang, onEvent);
      } catch {
        sessionRef.current = null;
        setError(t("chat.error"));
      } finally {
        patch((m) => ({ ...m, tool: null }));
        setStreaming(false);
      }
    },
    [streaming, apiLang, t],
  );

  return (
    <section className="chat">
      {messages.length === 0 && (
        <div className="intro">
          <p>{t("welcome")}</p>
          <ul className="chips">
            {[1, 2, 3].map((n) => (
              <li key={n}>
                <button type="button" className="chip" disabled={streaming} onClick={() => void send(t(`chat.suggestion${n}`))}>
                  {t(`chat.suggestion${n}`)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="messages" aria-live="polite">
        {messages.map((m) => {
          const citations = m.artifacts.filter((a) => a.kind === "citations");
          const others = m.artifacts.filter((a) => a.kind !== "citations");
          return (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="bubble">
                {m.role === "user" ? <p>{m.text}</p> : <Markdown text={m.text} />}
                {m.tool && (
                  <p className="tool-status">
                    {KNOWN_TOOLS.includes(m.tool) ? t(`tool.${m.tool}`) : t("tool.working")}
                  </p>
                )}
              </div>
              {others.map((a, i) => (
                <ArtifactView key={i} artifact={a} />
              ))}
              {citations.map((a, i) => (a.kind === "citations" ? <CitationList key={i} items={a.data.items} /> : null))}
            </div>
          );
        })}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div ref={endRef} />
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.placeholder")}
          disabled={streaming}
        />
        <button type="submit" disabled={streaming || !input.trim()}>
          {t("chat.send")}
        </button>
        <button type="button" className="secondary" disabled={streaming} onClick={() => void send(t("chat.brokerMessage"))}>
          {t("chat.contactBroker")}
        </button>
      </form>
    </section>
  );
}
