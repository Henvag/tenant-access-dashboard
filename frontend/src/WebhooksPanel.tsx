import { FormEvent, useEffect, useState } from "react";
import {
  createWebhook,
  deleteWebhook,
  listWebhookDeliveries,
  listWebhooks,
  sendTestWebhook,
  WebhookDelivery,
  WebhookList,
} from "./api";
import CopyButton from "./CopyButton";
import { messageForApiError, relativeTime } from "./format";
import { useLang } from "./i18n";

const STATUS_CLASS: Record<WebhookDelivery["status"], string> = {
  succeeded: "pill pill-xs pill-ok",
  pending: "pill pill-xs pill-warn",
  failed: "pill pill-xs pill-danger",
};

export default function WebhooksPanel() {
  const { lang, t } = useLang();
  const [data, setData] = useState<WebhookList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [pick, setPick] = useState(false);
  const [chosen, setChosen] = useState<string[]>([]);
  const [secret, setSecret] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  useEffect(() => {
    void listWebhooks()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "error"));
  }, []);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "error");
    } finally {
      setBusy(null);
    }
  }

  async function showDeliveries(id: string) {
    setDeliveries(await listWebhookDeliveries(id));
    setOpenId(id);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void run("create", async () => {
      const created = await createWebhook(url.trim(), pick && chosen.length ? chosen : null);
      const { secret: plain, ...endpoint } = created;
      setSecret(plain);
      setData((current) =>
        current ? { ...current, endpoints: [...current.endpoints, endpoint] } : current,
      );
      setUrl("");
      setPick(false);
      setChosen([]);
    });
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{t("webhooks.title")}</h2>
          <p className="hint">{t("webhooks.hint")}</p>
        </div>
      </div>
      {error ? (
        <p className="banner error" role="alert">
          {messageForApiError(error, lang)}
        </p>
      ) : null}
      {secret ? (
        <div className="banner info secret-banner">
          <p>{t("webhooks.secretOnce")}</p>
          <div className="secret-value">
            <code className="mono secret">{secret}</code>
            <CopyButton value={secret} />
          </div>
          <button type="button" className="link" onClick={() => setSecret(null)}>
            {t("apps.done")}
          </button>
        </div>
      ) : null}

      {data && data.endpoints.length ? (
        <ul className="app-list">
          {data.endpoints.map((endpoint) => (
            <li className="app-row webhook-row" key={endpoint.id}>
              <div className="app-row-main">
                <div className="app-row-text">
                  <div className="app-row-title">
                    <code className="mono">{endpoint.url}</code>
                  </div>
                  <div className="app-row-meta">
                    <span className="hint">
                      {endpoint.event_types
                        ? t("webhooks.someEvents", { count: String(endpoint.event_types.length) })
                        : t("webhooks.allEvents")}
                    </span>
                    <span className="hint">
                      {t("webhooks.secretHint", { hint: endpoint.secret_hint })}
                    </span>
                  </div>
                </div>
              </div>
              <div className="row-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={busy !== null}
                  onClick={() =>
                    void run(`test-${endpoint.id}`, async () => {
                      await sendTestWebhook(endpoint.id);
                      await showDeliveries(endpoint.id);
                    })
                  }
                >
                  {busy === `test-${endpoint.id}` ? t("webhooks.sending") : t("webhooks.test")}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={busy !== null}
                  aria-expanded={openId === endpoint.id}
                  onClick={() =>
                    openId === endpoint.id
                      ? setOpenId(null)
                      : void run(`log-${endpoint.id}`, () => showDeliveries(endpoint.id))
                  }
                >
                  {t("webhooks.deliveries")}
                </button>
                {confirmDelete === endpoint.id ? (
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    disabled={busy !== null}
                    onClick={() =>
                      void run(`delete-${endpoint.id}`, async () => {
                        await deleteWebhook(endpoint.id);
                        setConfirmDelete(null);
                        if (openId === endpoint.id) setOpenId(null);
                        setData((current) =>
                          current
                            ? {
                                ...current,
                                endpoints: current.endpoints.filter((e) => e.id !== endpoint.id),
                              }
                            : current,
                        );
                      })
                    }
                  >
                    {t("webhooks.confirmDelete")}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy !== null}
                    onClick={() => setConfirmDelete(endpoint.id)}
                  >
                    {t("webhooks.delete")}
                  </button>
                )}
              </div>
              {openId === endpoint.id ? (
                <div className="table-wrap delivery-log">
                  {deliveries.length ? (
                    <table className="table">
                      <thead>
                        <tr>
                          <th>{t("audit.event")}</th>
                          <th>{t("webhooks.status")}</th>
                          <th>{t("webhooks.response")}</th>
                          <th className="num">{t("webhooks.attempts")}</th>
                          <th>{t("webhooks.when")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {deliveries.map((row) => (
                          <tr key={row.id}>
                            <td>
                              <code className="mono">{row.event_type}</code>
                            </td>
                            <td>
                              <span className={STATUS_CLASS[row.status]}>
                                {t(`webhooks.status.${row.status}`)}
                              </span>
                            </td>
                            <td>{row.response_status ?? row.last_error ?? "-"}</td>
                            <td className="num">{row.attempts}</td>
                            <td>{relativeTime(row.last_attempt_at ?? row.created_at, lang)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="hint">{t("webhooks.noDeliveries")}</p>
                  )}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : data ? (
        <p className="hint">{t("webhooks.empty")}</p>
      ) : null}

      {data && data.endpoints.length < data.max_endpoints ? (
        <form className="webhook-form" onSubmit={submit}>
          <label className="field">
            <span>{t("webhooks.url")}</span>
            <input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com/webhooks/tenant-access"
              autoComplete="off"
              spellCheck={false}
              required
            />
          </label>
          <label className="check-row">
            <input type="checkbox" checked={pick} onChange={(event) => setPick(event.target.checked)} />
            <span>{t("webhooks.choose")}</span>
          </label>
          {pick ? (
            <ul className="check-list event-list">
              {data.event_types.map((type) => (
                <li key={type}>
                  <label className={chosen.includes(type) ? "check-row checked" : "check-row"}>
                    <input
                      type="checkbox"
                      checked={chosen.includes(type)}
                      onChange={(event) =>
                        setChosen((current) =>
                          event.target.checked
                            ? [...current, type]
                            : current.filter((item) => item !== type),
                        )
                      }
                    />
                    <code className="mono">{type}</code>
                  </label>
                </li>
              ))}
            </ul>
          ) : null}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={busy !== null || !url.trim() || (pick && chosen.length === 0)}
          >
            {t("webhooks.add")}
          </button>
        </form>
      ) : null}
    </section>
  );
}
