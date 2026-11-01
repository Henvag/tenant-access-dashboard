import { FormEvent, useEffect, useState } from "react";
import {
  addDomain,
  CompanyDomain,
  CompanyDomains,
  listDomains,
  removeDomain,
  setSignInPolicy,
  verifyDomain,
} from "./api";
import CopyButton from "./CopyButton";
import { formatTimestamp, messageForApiError } from "./format";
import { useLang } from "./i18n";

type Props = { isOwner: boolean; tenantName: string };

export default function DomainsPanel({ isOwner, tenantName }: Props) {
  const { lang, t } = useLang();
  const [data, setData] = useState<CompanyDomains | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    void listDomains()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "error"));
  }, []);

  function replace(row: CompanyDomain) {
    setData((current) =>
      current
        ? { ...current, domains: current.domains.map((d) => (d.id === row.id ? row : d)) }
        : current,
    );
  }

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "error");
    } finally {
      setBusy(null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;
    void run("add", async () => {
      const row = await addDomain(value);
      setData((current) => (current ? { ...current, domains: [...current.domains, row] } : current));
      setDraft("");
    });
  }

  if (!data) {
    return (
      <section className="card">
        <div className="card-head">
          <div>
            <h2>{t("domains.title")}</h2>
          </div>
        </div>
        {error ? <p className="banner error">{messageForApiError(error, lang)}</p> : null}
      </section>
    );
  }

  const canAdd = isOwner && !data.personal_workspace && data.domains.length < data.max_domains;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{t("domains.title")}</h2>
          <p className="hint">{t("domains.hint", { tenant: tenantName })}</p>
        </div>
      </div>
      {error ? (
        <p className="banner error" role="alert">
          {messageForApiError(error, lang)}
        </p>
      ) : null}
      {notice ? <p className="banner ok">{notice}</p> : null}

      {data.personal_workspace ? (
        <p className="hint">{t("domains.personal")}</p>
      ) : (
        <>
          <ul className="app-list domain-list">
            <li className="app-row">
              <div className="app-row-main">
                <div className="app-row-text">
                  <div className="app-row-title">
                    <span className="name-text mono-inline">{data.primary_domain}</span>
                    <span className="pill pill-xs pill-ok">{t("domains.verified")}</span>
                  </div>
                  <div className="app-row-meta">
                    <span className="hint">{t("domains.primaryHint")}</span>
                  </div>
                </div>
              </div>
            </li>
            {data.domains.map((row) => (
              <li className="app-row" key={row.id}>
                <div className="app-row-main">
                  <div className="app-row-text">
                    <div className="app-row-title">
                      <span className="name-text mono-inline">{row.domain}</span>
                      {row.verified ? (
                        <span className="pill pill-xs pill-ok">{t("domains.verified")}</span>
                      ) : (
                        <span className="pill pill-xs pill-warn">{t("domains.pending")}</span>
                      )}
                    </div>
                    {row.verified ? (
                      <div className="app-row-meta">
                        <span className="hint">
                          {t("domains.verifiedAt", { when: formatTimestamp(row.verified_at, lang) })}
                        </span>
                      </div>
                    ) : (
                      <div className="dns-record">
                        <p className="hint">{t("domains.instructions")}</p>
                        <div className="kv-grid">
                          <div className="kv-row">
                            <span className="kv-label">{t("domains.recordType")}</span>
                            <code className="mono">TXT</code>
                          </div>
                          <div className="kv-row">
                            <span className="kv-label">{t("domains.recordName")}</span>
                            <code className="mono">{row.record_name}</code>
                            <CopyButton value={row.record_name} />
                          </div>
                          <div className="kv-row">
                            <span className="kv-label">{t("domains.recordValue")}</span>
                            <code className="mono">{row.record_value}</code>
                            <CopyButton value={row.record_value} />
                          </div>
                        </div>
                        {row.last_checked_at ? (
                          <p className="hint">
                            {t("domains.lastChecked", {
                              when: formatTimestamp(row.last_checked_at, lang),
                            })}
                          </p>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
                {isOwner ? (
                  <div className="row-actions">
                    {!row.verified ? (
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={busy !== null}
                        onClick={() =>
                          void run(`verify-${row.id}`, async () => {
                            try {
                              const updated = await verifyDomain(row.id);
                              replace(updated);
                              setNotice(t("domains.verifiedNotice", { domain: updated.domain }));
                            } catch (err) {
                              // Keep "last checked" fresh even when the record is missing.
                              void listDomains().then(setData).catch(() => undefined);
                              throw err;
                            }
                          })
                        }
                      >
                        {busy === `verify-${row.id}` ? t("domains.checking") : t("domains.check")}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={busy !== null}
                      onClick={() =>
                        void run(`remove-${row.id}`, async () => {
                          await removeDomain(row.id);
                          setData((current) =>
                            current
                              ? { ...current, domains: current.domains.filter((d) => d.id !== row.id) }
                              : current,
                          );
                        })
                      }
                    >
                      {t("domains.remove")}
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>

          {canAdd ? (
            <form className="inline-form" onSubmit={submit}>
              <label className="field">
                <span>{t("domains.add")}</span>
                <input
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="acme.no"
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              <button type="submit" className="btn btn-primary" disabled={busy !== null || !draft.trim()}>
                {t("domains.addButton")}
              </button>
            </form>
          ) : null}
          {!isOwner ? <p className="hint">{t("domains.ownerOnly")}</p> : null}

          <div className="policy-block">
            <label className="check-row policy-toggle">
              <input
                type="checkbox"
                checked={data.require_managed_accounts}
                disabled={!isOwner || busy !== null}
                onChange={(event) => {
                  const next = event.target.checked;
                  void run("policy", async () => {
                    setData(await setSignInPolicy(next));
                  });
                }}
              />
              <span>
                <strong>{t("domains.managedTitle")}</strong>
                <small className="hint">{t("domains.managedHint")}</small>
              </span>
            </label>
          </div>
        </>
      )}
    </section>
  );
}
