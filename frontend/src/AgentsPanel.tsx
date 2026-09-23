import { FormEvent, useEffect, useState } from "react";
import {
  AgentInput,
  AgentProvider,
  TeamAgent,
  createAgent,
  deleteAgent,
  listAgents,
  sendAgentMessage,
} from "./api";
import { messageForApiError } from "./format";
import { useLang } from "./i18n";
import { IconClaude, IconChatGpt, IconSparkle } from "./Icons";

type Props = {
  isAdmin: boolean;
  tenantName: string;
};

type ChatTurn = { role: "user" | "assistant"; content: string };

function ProviderMark({ provider }: { provider: AgentProvider }) {
  return provider === "openai" ? (
    <IconChatGpt className="agent-logo" />
  ) : (
    <IconClaude className="agent-logo" />
  );
}

const MODELS: Record<AgentProvider, { id: string; label: string }[]> = {
  openai: [
    { id: "gpt-6-astra", label: "GPT-6 Astra" },
    { id: "gpt-6-sol", label: "GPT-6 Sol" },
  ],
  anthropic: [
    { id: "claude-fable-5-1", label: "Claude Fable 5.1" },
    { id: "claude-opus-5", label: "Claude Opus 5" },
  ],
};

export default function AgentsPanel({ isAdmin, tenantName }: Props) {
  const { lang, t } = useLang();
  const [agents, setAgents] = useState<TeamAgent[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<AgentProvider>("openai");
  const [model, setModel] = useState(MODELS.openai[0].id);
  const [apiKey, setApiKey] = useState("");
  const [policy, setPolicy] = useState<AgentInput["access_policy"]>("everyone");

  useEffect(() => {
    let cancelled = false;
    listAgents()
      .then((rows) => {
        if (!cancelled) setAgents(rows);
      })
      .catch((err) => {
        if (!cancelled) {
          setAgents([]);
          setError(err instanceof Error ? err.message : "agent_not_found");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const active = (agents ?? []).find((agent) => agent.id === activeId) ?? null;

  function openAgent(agent: TeamAgent) {
    setActiveId(agent.id);
    setMessages([]);
    setDraft("");
    setError(null);
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const created = await createAgent({
        name: name.trim(),
        provider,
        model,
        api_key: apiKey.trim(),
        access_policy: policy,
      });
      setAgents((current) => [...(current ?? []), created]);
      setName("");
      setApiKey("");
      setShowForm(false);
      openAgent(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "agent_key_required");
    }
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    if (!active || !draft.trim() || sending) return;
    const next: ChatTurn[] = [...messages, { role: "user", content: draft.trim() }];
    setMessages(next);
    setDraft("");
    setSending(true);
    setError(null);
    try {
      const reply = await sendAgentMessage(active.id, next);
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
          <h2>{t("agents.title")}</h2>
          <p className="hint">{t("agents.hint", { tenant: tenantName })}</p>
        </div>
        {isAdmin ? (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm((open) => !open)}>
            <IconSparkle />
            {t("agents.add")}
          </button>
        ) : null}
      </div>

      {error ? <p className="banner error">{messageForApiError(error, lang)}</p> : null}

      {showForm && isAdmin ? (
        <form className="agent-form" onSubmit={(event) => void onCreate(event)}>
          <label className="field">
            <span>{t("agents.name")}</span>
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={80} required />
          </label>
          <label className="field">
            <span>{t("agents.provider")}</span>
            <select
              value={provider}
              onChange={(event) => {
                const next = event.target.value as AgentProvider;
                setProvider(next);
                setModel(MODELS[next][0].id);
              }}
            >
              <option value="openai">{t("agents.provider.openai")}</option>
              <option value="anthropic">{t("agents.provider.anthropic")}</option>
            </select>
          </label>
          <label className="field">
            <span>{t("agents.model")}</span>
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              {MODELS[provider].map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("agents.policy")}</span>
            <select
              value={policy}
              onChange={(event) => setPolicy(event.target.value as AgentInput["access_policy"])}
            >
              <option value="everyone">{t("policy.everyone")}</option>
              <option value="admins">{t("policy.admins")}</option>
            </select>
          </label>
          <label className="field agent-form-key">
            <span>{t("agents.key")}</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
              required
            />
            <small>{t("agents.keyHint")}</small>
          </label>
          <button type="submit" className="btn btn-primary">
            {t("agents.add")}
          </button>
        </form>
      ) : null}

      {agents && agents.length === 0 ? (
        <div className="empty">
          <h3>{t("agents.emptyTitle")}</h3>
          <p>{t("agents.emptyBody")}</p>
        </div>
      ) : (
        <ul className="agent-list">
          {(agents ?? []).map((agent) => (
            <li
              key={agent.id}
              className={agent.id === activeId ? "agent-row active" : "agent-row"}
              aria-current={agent.id === activeId ? "true" : undefined}
            >
              <ProviderMark provider={agent.provider} />
              <div className="agent-row-text">
                <strong>{agent.name}</strong>
                <span>
                  {agent.provider === "openai"
                    ? t("agents.provider.openai")
                    : t("agents.provider.anthropic")}
                  {" · "}
                  {agent.model}
                  {isAdmin ? ` · ${t("agents.keyEnds", { hint: agent.key_hint })}` : ""}
                </span>
              </div>
              {agent.id === activeId ? (
                <span className="pill pill-accent">{t("agents.current")}</span>
              ) : (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => openAgent(agent)}>
                  {t("agents.open")}
                </button>
              )}
              {isAdmin ? (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    void deleteAgent(agent.id).then(() => {
                      setAgents((current) => (current ?? []).filter((row) => row.id !== agent.id));
                      if (activeId === agent.id) {
                        setActiveId(null);
                        setMessages([]);
                      }
                    });
                  }}
                >
                  {t("agents.remove")}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {active ? (
        <div className="agent-chat">
          <div className="agent-chat-head">
            <ProviderMark provider={active.provider} />
            <div>
              <p className="org-kicker">{t("agents.current")}</p>
              <strong>{t("agents.sendingTo", { name: active.name })}</strong>
              <span>
                {active.provider === "openai"
                  ? t("agents.provider.openai")
                  : t("agents.provider.anthropic")}
                {" · "}
                {active.model}
              </span>
            </div>
          </div>
          <div className="agent-thread">
            {messages.map((turn, index) => (
              <p key={`${turn.role}-${index}`} className={turn.role === "user" ? "agent-bubble me" : "agent-bubble"}>
                {turn.content}
              </p>
            ))}
          </div>
          <form className="agent-compose" onSubmit={(event) => void onSend(event)}>
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("agents.chatPlaceholder")}
              maxLength={8000}
              disabled={sending}
            />
            <button type="submit" className="btn btn-primary" disabled={sending || !draft.trim()}>
              {sending ? t("agents.sending") : t("agents.send")}
            </button>
          </form>
        </div>
      ) : null}
    </section>
  );
}
