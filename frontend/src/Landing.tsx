import { useEffect, useState } from "react";
import { lookupPublicInvite, loginUrl, PublicInvite } from "./api";
import BrandMark from "./BrandMark";
import { AppDenial, messageForAppDenial, messageForAuthError } from "./format";
import { useLang } from "./i18n";
import { IconGlobe, IconGoogle, IconLock, IconMicrosoft, IconPlug } from "./Icons";
import LanguageToggle from "./LanguageToggle";
import SignupForm from "./SignupForm";
import companiesIsolatedMark from "./assets/companies-isolated.jpg";
import idpPairMark from "./assets/google-microsoft.png";

type Tab = "signin" | "register";

type Props = {
  initialErrorCode: string | null;
  initialTab: Tab;
  denial?: AppDenial | null;
  continueApp?: string | null;
  inviteToken?: string | null;
};

export default function Landing({
  initialErrorCode,
  initialTab,
  denial = null,
  continueApp = null,
  inviteToken = null,
}: Props) {
  const { lang, t } = useLang();
  const [tab, setTab] = useState<Tab>(initialTab);
  const [errorCode, setErrorCode] = useState<string | null>(initialErrorCode);
  const [noticeDomain, setNoticeDomain] = useState<string | null>(null);
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const error = denial ? messageForAppDenial(denial, lang) : messageForAuthError(errorCode, lang);

  useEffect(() => {
    if (!inviteToken) return;
    let cancelled = false;
    lookupPublicInvite(inviteToken)
      .then((info) => {
        if (!cancelled) {
          setInvite(info);
          setTab("signin");
        }
      })
      .catch(() => {
        if (!cancelled) setErrorCode("invite_not_found");
      });
    return () => {
      cancelled = true;
    };
  }, [inviteToken]);

  return (
    <main className="landing">
      <div className="landing-lang">
        <LanguageToggle />
      </div>

      <div className="landing-hero">
        <section className="landing-intro">
          <div className="brand brand-hero">
            <BrandMark size={40} />
            <span className="brand-name">{t("brand")}</span>
          </div>

          <h1>{t("landing.title")}</h1>
          <p className="landing-lede">{t("landing.lede")}</p>
        </section>

        <section className="landing-card">
          <div className="tabs" role="tablist" aria-label={t("tabs.label")}>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "signin"}
              className={tab === "signin" ? "tab active" : "tab"}
              onClick={() => setTab("signin")}
            >
              {t("tabs.signin")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "register"}
              className={tab === "register" ? "tab active" : "tab"}
              onClick={() => setTab("register")}
            >
              {t("tabs.register")}
            </button>
          </div>

          {invite ? (
            <div className="banner info" role="status">
              <IconShield width={16} height={16} />
              <div>
                <strong>{t("landing.invite", { tenant: invite.tenant_name })}</strong>
                <p className="banner-sub">
                  {t("landing.inviteHint", { domain: invite.workspace_domain })}
                </p>
              </div>
            </div>
          ) : null}
          {continueApp ? (
            <div className="banner info" role="status">
              <IconPlug width={16} height={16} />
              <div>
                <strong>{t("landing.continue", { app: continueApp })}</strong>
                <p className="banner-sub">{t("landing.continueHint")}</p>
              </div>
            </div>
          ) : null}
          {error ? (
            <p className="banner error" role="alert">
              {error}
            </p>
          ) : null}
          {noticeDomain ? (
            <p className="banner ok" role="status">
              {t("notice.registered", { domain: noticeDomain })}
            </p>
          ) : null}

          {tab === "signin" ? (
            <div className="tab-panel">
              <h2>{t("signin.title")}</h2>
              <p className="hint">{t("signin.hint")}</p>
              <div className="signin-actions">
                <a className="btn btn-google btn-block" href={loginUrl("google")}>
                  <IconGoogle />
                  {t("signin.google")}
                </a>
                <a className="btn btn-microsoft btn-block" href={loginUrl("microsoft")}>
                  <IconMicrosoft />
                  {t("signin.microsoft")}
                </a>
              </div>
              <p className="fineprint">
                <IconGlobe width={14} height={14} />
                {t("signin.new")}{" "}
                <button type="button" className="link" onClick={() => setTab("register")}>
                  {t("signin.registerFirst")}
                </button>
                .
              </p>
            </div>
          ) : (
            <div className="tab-panel">
              <h2>{t("register.title")}</h2>
              <p className="hint">{t("register.hint")}</p>
              <SignupForm
                onCreated={(domain) => {
                  setErrorCode(null);
                  setNoticeDomain(domain);
                  setTab("signin");
                }}
              />
            </div>
          )}
        </section>
      </div>

      <section className="landing-features" aria-labelledby="landing-features-title">
        <h2 id="landing-features-title">{t("landing.featuresTitle")}</h2>
        <ul className="feature-list">
          <li>
            <span className="feature-icon feature-icon-wide">
              <img src={idpPairMark} alt="" width={26} height={26} />
            </span>
            <div>
              <strong>{t("feature.google.title")}</strong>
              <span>{t("feature.google.body")}</span>
            </div>
          </li>
          <li>
            <span className="feature-icon feature-icon-wide">
              <img src={companiesIsolatedMark} alt="" width={26} height={26} />
            </span>
            <div>
              <strong>{t("feature.isolated.title")}</strong>
              <span>{t("feature.isolated.body")}</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">
              <IconLock />
            </span>
            <div>
              <strong>{t("feature.roles.title")}</strong>
              <span>{t("feature.roles.body")}</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">
              <IconPlug />
            </span>
            <div>
              <strong>{t("feature.apps.title")}</strong>
              <span>{t("feature.apps.body")}</span>
            </div>
          </li>
        </ul>
      </section>
    </main>
  );
}
