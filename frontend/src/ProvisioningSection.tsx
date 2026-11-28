import { FormEvent, useEffect, useState } from "react";
import {
  AppAccount,
  AppAccountStatus,
  clearAppProvisioning,
  listAppAccounts,
  RegisteredApp,
  setAppProvisioning,
  syncAppAccounts,
} from "./api";
import { formatTimestamp, messageForApiError } from "./format";
import { TKey, useLang } from "./i18n";

const STATUS: Record<AppAccountStatus, { key: TKey; pill: string }> = {
  pending: { key: "provision.status.pending", pill: "pill" },
  active: { key: "provision.status.active", pill: "pill pill-ok" },
  deactivated: { key: "provision.status.deactivated", pill: "pill pill-warn" },
  none: { key: "provision.status.none", pill: "pill" },
  failed: { key: "provision.status.failed", pill: "pill pill-danger" },
};

/** Slack: create people's accounts when they get access, deactivate them when it ends. */
export default function ProvisioningSection({
  app,
  onUpdated,
}: {
  app: RegisteredApp;
  onUpdated: (app: RegisteredApp) => void;
}) {
  const { lang, t } = useLang();
  const [token, setToken] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<AppAccount[] | null>(null);
  const connected = app.provision_kind !== null;

  function fail(err: unknown) {
    setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
  }

  useEffect(() => {
    if (!connected) {
      setAccounts(null);
      return;
    }
    let cancelled = false;
    listAppAccounts(app.id)
      .then((rows) => !cancelled && setAccounts(rows))
      .catch((err) => !cancelled && fail(err));
    return () => {
      cancelled = true;
    };
  }, [app.id, connected]);

  async function run(action: () => Promise<void>) {
    setPending(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      fail(err);
    } finally {
      setPending(false);
    }
  }

  function connect(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      onUpdated(await setAppProvisioning(app.id, { kind: "slack", token: token.trim() }));
      setToken("");
    });
  }

  function errorText(code: string | null): string | null {
    if (!code) return null;
    const text = messageForApiError(code, lang);
    return text === code ? t("provision.errorCode", { code }) : text;
  }

  return (
    <section className="signout-section">
      <h3>{t("provision.title")}</h3>
      <p className="hint">{t("provision.hint")}</p>
      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}
      {connected ? (
        <>
          <div className="signout-connected">
            <div>
              <strong>{t("provision.connected")}</strong>
              {app.provision_key_hint ? (
                <p className="hint">{t("signout.keyEnding", { hint: app.provision_key_hint })}</p>
              ) : null}
            </div>
            <div className="provision-actions">
              <button
                type="button"
                className="btn btn-ghost"
                disabled={pending}
                onClick={() => void run(async () => setAccounts(await syncAppAccounts(app.id)))}
              >
                {t("provision.sync")}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={pending}
                onClick={() => {
                  if (!window.confirm(t("provision.removeConfirm"))) return;
                  void run(async () => onUpdated(await clearAppProvisioning(app.id)));
                }}
              >
                {t("signout.remove")}
              </button>
            </div>
          </div>
          {accounts === null ? null : accounts.length === 0 ? (
            <p className="hint">{t("provision.noAccounts")}</p>
          ) : (
            <ul className="provision-list">
              {accounts.map((row, index) => (
                <li key={`${row.email}-${index}`}>
                  <div>
                    <span>{row.email || t("audit.deletedPerson")}</span>
                    <small className="hint">
                      {row.queued
                        ? t("provision.queued")
                        : row.synced_at
                          ? t("provision.checked", { when: formatTimestamp(row.synced_at, lang) })
                          : null}
                      {row.last_error ? ` ${errorText(row.last_error)}` : null}
                    </small>
                  </div>
                  <span className={STATUS[row.status]?.pill ?? "pill"}>
                    {t(STATUS[row.status]?.key ?? "provision.status.pending")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <form onSubmit={connect} className="app-form">
          <label className="field">
            <span>{t("provision.token")}</span>
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              type="password"
              autoComplete="off"
              placeholder="xoxp-…"
              required
            />
            <small>{t("provision.tokenHint")}</small>
          </label>
          <div className="modal-actions">
            <button type="submit" className="btn btn-primary" disabled={pending}>
              {pending ? t("signout.checking") : t("signout.connect")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
