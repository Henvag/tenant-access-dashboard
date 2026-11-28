import { useEffect, useState } from "react";
import { RegisteredApp } from "./api";
import CopyButton from "./CopyButton";
import { useLang } from "./i18n";

/** The values an admin pastes into a SAML app (Slack, Zoom, ...) to sign in through us. */
export default function SamlSetupSection({ app }: { app: RegisteredApp }) {
  const { t } = useLang();
  const [certificate, setCertificate] = useState<string | null>(null);

  useEffect(() => {
    if (!app.saml_certificate_url) return;
    let cancelled = false;
    fetch(app.saml_certificate_url, { credentials: "include" })
      .then((r) => (r.ok ? r.text() : null))
      .then((text) => {
        if (!cancelled) setCertificate(text);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [app.saml_certificate_url]);

  const rows: Array<[string, string | null]> = [
    [t("saml.ssoUrl"), app.saml_sso_url],
    [t("saml.issuer"), app.saml_issuer],
    [t("saml.metadata"), app.saml_metadata_url],
  ];

  return (
    <section className="signout-section saml-setup">
      <h3>{t("saml.title")}</h3>
      <p className="hint">{t("saml.hint")}</p>
      <div className="kv-grid">
        {rows.map(([label, value]) =>
          value ? (
            <div className="kv-row" key={label}>
              <span className="kv-label">{label}</span>
              <code className="mono">{value}</code>
              <CopyButton value={value} />
            </div>
          ) : null,
        )}
        <div className="kv-row">
          <span className="kv-label">{t("saml.certificate")}</span>
          {certificate ? (
            <>
              <code className="mono saml-cert">{certificate.trim()}</code>
              <CopyButton value={certificate.trim()} />
            </>
          ) : (
            <span className="hint">…</span>
          )}
        </div>
      </div>
      {app.saml_certificate_url ? (
        <p className="hint">
          <a className="link" href={app.saml_certificate_url} download>
            {t("saml.download")}
          </a>
        </p>
      ) : null}
      {app.saml_entity_id === "https://slack.com" ? (
        <p className="hint tip-box">{t("saml.slackTip")}</p>
      ) : (
        <p className="hint tip-box">{t("saml.genericTip")}</p>
      )}
    </section>
  );
}
