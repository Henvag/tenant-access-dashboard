import { FormEvent, useEffect, useState } from "react";
import {
  AskStatus,
  clearAsk,
  configureAsk,
  getAskStatus,
  sendAskMessage,
  setAskEnabled,
} from "./api";
import geminiLogo from "./assets/gemini.svg";
import ChatBubble from "./ChatBubble";
import ChatThinking from "./ChatThinking";
import { messageForApiError } from "./format";
import { TKey, useLang } from "./i18n";

type Props = {
  isAdmin: boolean;
  tenantName: string;
  initialConfigured: boolean;
  onConfiguredChange: (configured: boolean) => void;
};

type ChatTurn = { role: "user" | "assistant"; content: string };

const ASK_MODELS = [
  { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash-Lite" },
  { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash" },
];

const SUGGESTIONS_ADMIN: TKey[] = [
  "ask.chip.owner",
  "ask.chip.apps",
  "ask.chip.upgrade",
  "ask.chip.recent",
];

const SUGGESTIONS_MEMBER: TKey[] = [
  "ask.chip.whoami",
  "ask.chip.apps",
  "ask.chip.openApps",
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
  const [showKeyForm, setShowKeyForm] = useState(false);

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
  const enabled = status?.enabled ?? true;
  const source = status?.source ?? null;
  const canTurnOff = status?.can_turn_off ?? false;

  async function onToggleEnabled(next: boolean) {
    setError(null);
    try {
      const updated = await setAskEnabled(next);
      setStatus(updated);
      onConfiguredChange(updated.configured);
      if (!next) setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "owner_required");
    }
  }
  const chips = isAdmin ? SUGGESTIONS_ADMIN : SUGGESTIONS_MEMBER;

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!isAdmin || !apiKey.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const next = await configureAsk({ api_key: apiKey.trim(), model });
      setStatus(next);
      onConfiguredChange(next.configured);
      setApiKey("");
      setShowKeyForm(false);
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
      const next = await getAskStatus();
      setStatus(next);
      onConfiguredChange(next.configured);
      if (!next.configured) setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ask_not_configured");
    }
  }

  async function sendText(text: string) {
    const cleaned = text.trim();
    if (!configured || !cleaned || sending) return;
    const prior = messages;
    const next: ChatTurn[] = [...prior, { role: "user", content: cleaned }];
    setMessages(next);
    setDraft("");
    setSending(true);
    setError(null);
    try {
      const reply = await sendAskMessage(next);
      setMessages([...next, { role: "assistant", content: reply.content }]);
      if (source === "builtin") {
        setStatus((prev) =>
          prev ? { ...prev, used_today: (prev.used_today ?? 0) + 1 } : prev,
        );
      }
    } catch (err) {
      setMessages(prior);
      setDraft(cleaned);
      setError(err instanceof Error ? err.message : "agent_chat_failed");
    } finally {
      setSending(false);
    }
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    await sendText(draft);
  }

  const keyForm = (
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
  );

  const ownerSwitch = canTurnOff ? (
    <button
      type="button"
      className="btn btn-ghost btn-sm"
      onClick={() => void onToggleEnabled(!enabled)}
    >
      {enabled ? t("ask.turnOff") : t("ask.turnOn")}
    </button>
  ) : null;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{t("ask.title")}</h2>
          <p className="hint">{t("ask.hint", { tenant: tenantName })}</p>
        </div>
        {source === "own_key" ? (
          <img className="agent-logo ask-mark" src={geminiLogo} alt="" width={28} height={28} />
        ) : null}
      </div>

      {error ? (
        <p
          className={`banner ${
            error === "ask_rate_limited" || error === "ask_daily_limit" ? "info" : "error"
          }`}
          role="alert"
        >
          {messageForApiError(error, lang)}
        </p>
      ) : null}

      {!enabled ? (
        <div className="ask-setup">
          <h3>{t("ask.offTitle")}</h3>
          <p>{canTurnOff ? t("ask.offBodyOwner") : t("ask.offBody")}</p>
          {ownerSwitch}
        </div>
      ) : !configured ? (
        <div className="ask-setup">
          <h3>{t("ask.emptyTitle")}</h3>
          <p>{isAdmin ? t("ask.emptyBodyAdmin") : t("ask.emptyBody")}</p>
          {isAdmin ? keyForm : null}
        </div>
      ) : (
        <>
          <div className="ask-admin-bar">
            <span className="hint">
              {source === "own_key"
                ? isAdmin
                  ? t("ask.configured", {
                      model: status?.model ?? model,
                      hint: status?.key_hint ?? "····",
                    })
                  : null
                : t("ask.builtin", { model: status?.model ?? "Gemma 4" })}
              {source === "builtin" && status?.daily_limit ? (
                <>
                  {" · "}
                  {t("ask.usage", {
                    used: String(Math.min(status.used_today ?? 0, status.daily_limit)),
                    limit: String(status.daily_limit),
                  })}
                </>
              ) : null}
            </span>
            {isAdmin && source === "own_key" ? (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onClear()}>
                {t("ask.remove")}
              </button>
            ) : null}
            {isAdmin && source === "builtin" && !showKeyForm ? (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowKeyForm(true)}
              >
                {t("ask.ownKeyToggle")}
              </button>
            ) : null}
            {ownerSwitch}
          </div>
          {isAdmin && source === "builtin" && showKeyForm ? (
            <div className="ask-setup">
              <p>{t("ask.ownKeyBody")}</p>
              {keyForm}
            </div>
          ) : null}
          <div className="agent-chat ask-chat">
            <div className="agent-thread">
              {messages.length === 0 && !sending ? (
                <div className="ask-empty">
                  <p className="hint ask-starter">{t("ask.starter")}</p>
                  <div className="ask-chips" role="group" aria-label={t("ask.chipsLabel")}>
                    {chips.map((key) => (
                      <button
                        key={key}
                        type="button"
                        className="ask-chip"
                        disabled={sending}
                        onClick={() => void sendText(t(key))}
                      >
                        {t(key)}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((turn, index) => (
                  <ChatBubble key={`${turn.role}-${index}`} role={turn.role} content={turn.content} />
                ))
              )}
              <ChatThinking active={sending} />
            </div>
            {messages.length > 0 && !sending ? (
              <div className="ask-chips ask-chips-inline" role="group" aria-label={t("ask.chipsLabel")}>
                {chips.map((key) => (
                  <button
                    key={key}
                    type="button"
                    className="ask-chip"
                    onClick={() => void sendText(t(key))}
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
            ) : null}
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
