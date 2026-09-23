import { useState } from "react";
import { clearCompanyLogo, fetchCompanyLogo, uploadCompanyLogo } from "./api";
import { messageForApiError } from "./format";
import { useLang } from "./i18n";

type Props = {
  isOwner: boolean;
  name: string;
  domain: string;
  logoUrl: string | null;
  onLogo: (url: string | null) => void;
};

export default function OrganizationPanel({ isOwner, name, domain, logoUrl, onLogo }: Props) {
  const { lang, t } = useLang();
  const [error, setError] = useState<string | null>(null);
  const initial = name.trim().charAt(0).toUpperCase() || "T";

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{t("org.title")}</h2>
          <p className="hint">{t("org.hint")}</p>
        </div>
      </div>
      {error ? <p className="banner error">{messageForApiError(error, lang)}</p> : null}
      <div className="org-brand">
        <div className="org-logo-frame">
          {logoUrl ? (
            <img src={logoUrl} alt="" />
          ) : (
            <span>{initial}</span>
          )}
        </div>
        <div className="org-brand-copy">
          <p className="org-kicker">{t("org.logo")}</p>
          <strong>{name}</strong>
          <p className="hint">@{domain}</p>
          <p className="hint">{t("org.requirements")}</p>
          {isOwner ? (
            <div className="org-brand-actions">
              <label className="btn btn-primary">
                {logoUrl ? t("logo.replace") : t("logo.change")}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (!file) return;
                    setError(null);
                    void uploadCompanyLogo(file)
                      .then(() => fetchCompanyLogo())
                      .then((url) => {
                        onLogo(url);
                      })
                      .catch((err) => {
                        setError(err instanceof Error ? err.message : "logo_type");
                      });
                  }}
                />
              </label>
              {logoUrl ? (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    setError(null);
                    void clearCompanyLogo()
                      .then(() => onLogo(null))
                      .catch((err) => {
                        setError(err instanceof Error ? err.message : "logo_type");
                      });
                  }}
                >
                  {t("logo.clear")}
                </button>
              ) : null}
            </div>
          ) : (
            <p className="hint">{t("org.ownerOnly")}</p>
          )}
        </div>
      </div>
    </section>
  );
}
