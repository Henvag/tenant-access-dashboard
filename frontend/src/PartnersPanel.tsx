import { FormEvent, useEffect, useState } from "react";
import { invitePartner, listPartners, Partners, revokePartnerInvite } from "./api";
import { formatTimestamp, messageForApiError } from "./format";
import { useLang } from "./i18n";

type Props = {
  tenantName: string;
  /** Called after an invite changes, so the audit list can refresh. */
  onChange?: () => void;
};

/** Owner-only: invite outside admins (partner mode) and cancel open invites. */
export default function PartnersPanel({ tenantName, onChange }: Props) {
  const { lang, t } = useLang();
  const [data, setData] = useState<Partners | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    void listPartners()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "error"));
  }, []);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      onChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "error");
    } finally {
      setBusy(null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const email = draft.trim();
    if (!email) return;
    void run("invite", async () => {
      const row = await invitePartner(email);
      setData((current) => (current ? { ...current, invites: [row, ...current.invites] } : current));
      setDraft("");
      setNotice(t("partners.invited", { email: row.email }));
    });
  }

  const used = data ? data.outside_admins + data.invites.length : 0;
  const full = data ? used >= data.limit : true;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{t("partners.title")}</h2>
          <p className="hint">{t("partners.hint", { tenant: tenantName })}</p>
          {data ? (
            <p className="hint">{t("partners.used", { used, limit: data.limit })}</p>
          ) : null}
        </div>
      </div>
      {error ? (
        <p className="banner error" role="alert">
          {messageForApiError(error, lang)}
        </p>
      ) : null}
      {notice ? (
        <p className="banner ok" role="status">
          {notice}
        </p>
      ) : null}

      {data && data.invites.length > 0 ? (
        <>
          <ul className="app-list">
            {data.invites.map((row) => (
              <li className="app-row" key={row.id}>
                <div className="app-row-main">
                  <div className="app-row-text">
                    <div className="app-row-title">
                      <span className="name-text">{row.email}</span>
                      <span className="pill pill-xs pill-warn">{t("partners.pending")}</span>
                    </div>
                    <div className="app-row-meta">
                      <span className="hint">
                        {t("partners.expires", { when: formatTimestamp(row.expires_at, lang) })}
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
                      void run(`revoke-${row.id}`, async () => {
                        await revokePartnerInvite(row.id);
                        setData((current) =>
                          current
                            ? { ...current, invites: current.invites.filter((i) => i.id !== row.id) }
                            : current,
                        );
                      })
                    }
                  >
                    {t("partners.revoke")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <p className="hint">
            {t("partners.howTo", { url: window.location.host, tenant: tenantName })}
          </p>
        </>
      ) : data ? (
        <p className="hint">{t("partners.none")}</p>
      ) : null}

      {data && !full ? (
        <form className="inline-form" onSubmit={submit}>
          <label className="field">
            <span>{t("partners.email")}</span>
            <input
              type="email"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="kari@itfirma.no"
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy !== null || !draft.trim()}>
            {t("partners.invite")}
          </button>
        </form>
      ) : null}
    </section>
  );
}
