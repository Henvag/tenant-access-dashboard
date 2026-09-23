import { FormEvent, useEffect, useState } from "react";
import {
  AskStatus,
  clearAsk,
  configureAsk,
  getAskStatus,
  sendAskMessage,
} from "./api";
import geminiLogo from "./assets/gemini.svg";
import ChatBubble from "./ChatBubble";
import ChatThinking from "./ChatThinking";
import { messageForApiError } from "./format";
import { useLang } from "./i18n";

type Props = {
  isAdmin: boolean;
  tenantName: string;
  initialConfigured: boolean;
  onConfiguredChange: (configured: boolean) => void;
};

type ChatTurn = { role: "user" | "assistant"; content: string };

const ASK_MODELS = [
  { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash" },
  { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash-Lite" },
];

export default function AskPanel({
  isAdmin,
  tenantName,
  initialConfigured,
  onConfiguredChange,
}: Props) {
  const { lang, t } = useLang();
  const [status, setStatus] = useState<AskStatus | null>(
    initialConfigured ? { configured: true, model: null, key_hint: null } : null,
  );
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(ASK_MODELS[0].id);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAskStatus()
      .then((next) => {
        if (!cancelled) {
          setStatus(next);
          onConfiguredChange(next.configured);
          if (next.model) setModel(next.model);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "ask_not_configured");
      });
    return () => {
      cancelled = true;
    };
  }, [onConfiguredChange]);

  const configured = status?.configured ?? initialConfigured;

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!isAdmin || !apiKey.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const next = await configureAsk({ api_key: apiKey.trim(), model });
      setStatus(next);
      onConfiguredChange(true);
      setApiKey("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "agent_key_required");
    } finally {
      setSaving(false);
    }
  }

  async function onClear() {
    if (!isAdmin) return;
    setError(null);
    try {
      await clearAsk();
      setStatus({ configured: false, model: null, key_hint: null });
      onConfiguredChange(false);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ask_not_configured");
    }
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    if (!configured || !draft.trim() || sending) return;
    const next: ChatTurn[] = [...messages, { role: "user", content: draft.trim() }];
    setMessages(next);
    setDraft("");
    setSending(true);
    setError(null);
    try {
      const reply = await sendAskMessage(next);
      setMessages([...next, { role: "assistant", content: reply.content }]);
    } catch (err) {
      setMessages(messages);
      setDraft(next[next.length - 1]?.content ?? "");
      setError(err instanceof Error ? err.message : "agent_chat_failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{t("ask.title")}</h2>
          <p className="hint">{t("ask.hint", { tenant: tenantName })}</p>
        </div>
        <img className="agent-logo ask-mark" src={geminiLogo} alt="" width={28} height={28} />
      </div>

      {error ? <p className="banner error">{messageForApiError(error, lang)}</p> : null}

      {!configured ? (
        <div className="ask-setup">
          <h3>{t("ask.emptyTitle")}</h3>
          <p>{isAdmin ? t("ask.emptyBodyAdmin") : t("ask.emptyBody")}</p>
          {isAdmin ? (
            <form className="agent-form" onSubmit={(event) => void onSave(event)}>
              <label className="field">
                <span>{t("ask.model")}</span>
                <select value={model} onChange={(event) => setModel(event.target.value)}>
                  {ASK_MODELS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field agent-form-key">
                <span>{t("ask.key")}</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="off"
                  required
                />
                <small>{t("ask.keyHint")}</small>
              </label>
              <button type="submit" className="btn btn-primary" disabled={saving || !apiKey.trim()}>
                {saving ? t("ask.saving") : t("ask.enable")}
              </button>
            </form>
          ) : null}
        </div>
      ) : (
        <>
          {isAdmin ? (
            <div className="ask-admin-bar">
              <span className="hint">
                {t("ask.configured", {
                  model: status?.model ?? model,
                  hint: status?.key_hint ?? "····",
                })}
              </span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onClear()}>
                {t("ask.remove")}
              </button>
            </div>
          ) : null}
          <div className="agent-chat ask-chat">
            <div className="agent-thread">
              {messages.length === 0 && !sending ? (
                <p className="hint ask-starter">{t("ask.starter")}</p>
              ) : (
                messages.map((turn, index) => (
                  <ChatBubble key={`${turn.role}-${index}`} role={turn.role} content={turn.content} />
                ))
              )}
              <ChatThinking active={sending} />
            </div>
            <form className="agent-compose" onSubmit={(event) => void onSend(event)}>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={t("ask.placeholder")}
                maxLength={8000}
                disabled={sending}
              />
              <button type="submit" className="btn btn-primary" disabled={sending || !draft.trim()}>
                {sending ? t("ask.sending") : t("ask.send")}
              </button>
            </form>
          </div>
        </>
      )}
    </section>
  );
}
