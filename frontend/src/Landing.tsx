import { useEffect, useRef, useState } from "react";
import {
  API_BASE,
  BillingPlan,
  demoUrl,
  listBillingPlans,
  lookupPublicInvite,
  loginUrl,
  PublicInvite,
} from "./api";
import AppMark from "./AppMark";
import BrandMark from "./BrandMark";
import { AppDenial, messageForAppDenial, messageForAuthError, workspaceLabel } from "./format";
import { TKey, useLang } from "./i18n";
import {
  IconCheck,
  IconClose,
  IconGlobe,
  IconGoogle,
  IconMenu,
  IconMicrosoft,
  IconPlay,
  IconPlug,
  IconShield,
} from "./Icons";
import LanguageToggle from "./LanguageToggle";
import ProductFilm from "./ProductFilm";
import SeparationFigure from "./SeparationFigure";
import SignupForm from "./SignupForm";

type Tab = "signin" | "register";

type Props = {
  initialErrorCode: string | null;
  initialTab: Tab;
  denial?: AppDenial | null;
  continueApp?: string | null;
  inviteToken?: string | null;
};

/** The page's sections in the order they appear; the nav lists them in the same order. */
const SECTIONS = [
  { id: "how", label: "landing.nav.how" },
  { id: "apps", label: "landing.nav.apps" },
  { id: "security", label: "landing.nav.security" },
  { id: "pricing", label: "landing.nav.pricing" },
  { id: "faq", label: "landing.nav.faq" },
] as const satisfies readonly { id: string; label: TKey }[];

type SectionId = (typeof SECTIONS)[number]["id"];

const APPS = ["Grafana", "Gitea", "Outline", "BookStack", "Portainer"];

const FAQ = [1, 2, 3, 4, 5, 6, 7] as const;

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

  const [plans, setPlans] = useState<BillingPlan[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    listBillingPlans()
      .then((list) => {
        if (!cancelled) setPlans(list);
      })
      .catch(() => {
        if (!cancelled) setPlans([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A link such as tenantaccess.me/#faq arrives before the page is drawn. Wait for the
  // plan list, which changes the height above the later sections, then jump once.
  const jumped = useRef(false);
  useEffect(() => {
    if (plans === null || jumped.current) return;
    jumped.current = true;
    const id = window.location.hash.slice(1);
    if (id) document.getElementById(id)?.scrollIntoView({ behavior: "instant" });
  }, [plans]);

  const toSignIn = () => setTab("signin");
  const toRegister = () => setTab("register");

  return (
    <main className="landing" id="top">
      <LandingNav onSignIn={toSignIn} />

      <div className="landing-hero">
        <section className="landing-intro" aria-labelledby="landing-title">
          <h1 id="landing-title">{t("landing.title")}</h1>
          <p className="landing-lede">{t("landing.lede")}</p>
          <div className="landing-actions">
            <DemoButton />
            <a className="btn btn-secondary" href="#signin" onClick={toRegister}>
              {t("landing.registerCta")}
            </a>
          </div>
          <p className="fineprint landing-actions-hint">{t("demo.ctaHint")}</p>
          <WorksWith />
        </section>

        <section className="landing-card" id="signin" tabIndex={-1} aria-label={t("tabs.label")}>
          <div className="tabs" role="tablist" aria-label={t("tabs.label")}>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "signin"}
              className={tab === "signin" ? "tab active" : "tab"}
              onClick={toSignIn}
            >
              {t("tabs.signin")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "register"}
              className={tab === "register" ? "tab active" : "tab"}
              onClick={toRegister}
            >
              {t("tabs.register")}
            </button>
          </div>

          {invite ? (
            <div className="banner info" role="status">
              {invite.has_logo ? (
                <img
                  className="invite-logo"
                  src={`${API_BASE}/public/invites/${encodeURIComponent(inviteToken || "")}/logo`}
                  alt=""
                  width={28}
                  height={28}
                />
              ) : (
                <IconShield width={16} height={16} />
              )}
              <div>
                <strong>{t("landing.invite", { tenant: invite.tenant_name })}</strong>
                <p className="banner-sub">
                  {t("landing.inviteHint", { domain: workspaceLabel(invite.workspace_domain) })}
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
                <button type="button" className="link" onClick={toRegister}>
                  {t("signin.registerFirst")}
                </button>
              </p>
            </div>
          ) : (
            <div className="tab-panel">
              <h2>{t("register.title")}</h2>
              <p className="hint">{t("register.hint")}</p>
              <SignupForm />
            </div>
          )}
        </section>
      </div>

      <section className="landing-section" id="how" aria-labelledby="how-title">
        <SectionHead id="how-title" title={t("how.title")} lede={t("how.lede")} />
        <ol className="steps">
          {([1, 2, 3] as const).map((n) => (
            <li key={n}>
              <span className="step-number" aria-hidden="true">
                {n}
              </span>
              <strong>{t(`how.step${n}.title`)}</strong>
              <p>{t(`how.step${n}.body`)}</p>
            </li>
          ))}
        </ol>
        <div className="landing-film">
          <div className="landing-film-head">
            <h3>{t("film.title")}</h3>
            <p className="hint">{t("film.lede")}</p>
          </div>
          <ProductFilm />
        </div>
      </section>

      <section className="landing-section" id="apps" aria-labelledby="apps-title">
        <SectionHead id="apps-title" title={t("landing.apps.title")} lede={t("feature.apps.body")} />
        <ul className="app-grid">
          {APPS.map((name) => (
            <li key={name}>
              <AppMark name={name} />
              <span>{name}</span>
            </li>
          ))}
          <li>
            <AppMark name="" />
            <span>{t("landing.apps.other")}</span>
          </li>
        </ul>
        <p className="app-accounts">
          <span className="feature-marks" aria-hidden="true">
            <IconGoogle width={16} height={16} />
            <IconMicrosoft width={16} height={16} />
          </span>
          {t("landing.apps.accounts")}
        </p>
      </section>

      <section className="landing-night" id="security" aria-labelledby="security-title">
        <div className="landing-night-inner">
          <SectionHead id="security-title" title={t("security.title")} lede={t("security.lede")} />
          <SeparationFigure />
          <ul className="security-list">
            {(["signin", "isolated", "audit", "hosting"] as const).map((key) => (
              <li key={key}>
                <strong>{t(`security.${key}.title`)}</strong>
                <p>{t(`security.${key}.body`)}</p>
                {key === "hosting" ? <a href="/privacy">{t("landing.privacy")}</a> : null}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Pricing plans={plans} onRegister={toRegister} />

      <section className="landing-section landing-faq" id="faq" aria-labelledby="faq-title">
        <SectionHead id="faq-title" title={t("faq.title")} />
        <div className="faq">
          {FAQ.map((n) => (
            <details key={n}>
              <summary>{t(`faq.q${n}`)}</summary>
              <p>
                {n === 2 ? t("feature.apps.body") : t(`faq.a${n}` as "faq.a1")}
                {n === 4 ? (
                  <>
                    {" "}
                    <a href="/privacy">{t("landing.privacy")}</a>
                  </>
                ) : null}
              </p>
            </details>
          ))}
        </div>
      </section>

      <section className="landing-final" aria-labelledby="final-title">
        <h2 id="final-title">{t("final.title")}</h2>
        <p className="landing-lede">{t("demo.ctaHint")}</p>
        <div className="landing-actions">
          <DemoButton />
          <a className="btn btn-secondary" href="#signin" onClick={toRegister}>
            {t("landing.registerCta")}
          </a>
        </div>
      </section>

      <footer className="landing-footer">
        <a className="landing-footer-brand" href="#top">
          <BrandMark size={20} />
          <span>{t("brand")}</span>
        </a>
        <a href="/privacy">{t("landing.privacy")}</a>
      </footer>
    </main>
  );
}

function SectionHead({ id, title, lede }: { id: string; title: string; lede?: string }) {
  return (
    <div className="section-head">
      <h2 id={id}>{title}</h2>
      {lede ? <p className="landing-lede">{lede}</p> : null}
    </div>
  );
}

/**
 * Sticky bar. Its links follow the order of the sections below and the link
 * of the section on screen is marked. Below 900px the links fold into a menu.
 */
function LandingNav({ onSignIn }: { onSignIn: () => void }) {
  const { t } = useLang();
  const [active, setActive] = useState<SectionId | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const targets = SECTIONS.map(({ id }) => document.getElementById(id)).filter(
      (el): el is HTMLElement => el !== null,
    );
    // A section counts as current while it crosses a line 40% down the screen.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(entry.target.id as SectionId);
        }
      },
      { rootMargin: "-40% 0px -59% 0px" },
    );
    targets.forEach((el) => observer.observe(el));
    const clearAtTop = () => {
      if (window.scrollY < 80) setActive(null);
    };
    window.addEventListener("scroll", clearAtTop, { passive: true });
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", clearAtTop);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const close = () => setOpen(false);

  return (
    <header className={open ? "site-nav open" : "site-nav"}>
      <div className="site-nav-bar">
        <a className="site-nav-brand" href="#top" aria-label={t("landing.nav.top")} onClick={close}>
          <BrandMark size={28} />
          <span aria-hidden="true">{t("brand")}</span>
        </a>
        <nav id="site-nav-links" className="site-nav-links" aria-label={t("landing.navLabel")}>
          <ul>
            {SECTIONS.map(({ id, label }) => (
              <li key={id}>
                <a href={`#${id}`} aria-current={active === id ? "true" : undefined} onClick={close}>
                  {t(label)}
                </a>
              </li>
            ))}
          </ul>
          <div className="site-nav-extra">
            <LanguageToggle />
            <a
              className="site-nav-signin"
              href="#signin"
              onClick={() => {
                onSignIn();
                close();
              }}
            >
              {t("landing.nav.signin")}
            </a>
          </div>
        </nav>
        <div className="site-nav-cta">
          <DemoButton compact />
          <button
            type="button"
            className="site-nav-toggle"
            aria-expanded={open}
            aria-controls="site-nav-links"
            aria-label={open ? t("landing.nav.close") : t("landing.nav.menu")}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <IconClose width={20} height={20} /> : <IconMenu width={20} height={20} />}
          </button>
        </div>
      </div>
    </header>
  );
}

function WorksWith() {
  const { t } = useLang();
  return (
    <div className="works-with">
      <span>{t("landing.worksWith")}</span>
      <ul>
        <li>
          <IconGoogle width={16} height={16} />
          Google
        </li>
        <li>
          <IconMicrosoft width={16} height={16} />
          Microsoft
        </li>
        {APPS.slice(0, 3).map((name) => (
          <li key={name}>
            <AppMark name={name} size="sm" />
            {name}
          </li>
        ))}
      </ul>
    </div>
  );
}

type Period = "monthly" | "yearly";

/**
 * Public plans as three cards. Team is the featured card on the night ground, and a
 * monthly/yearly switch shows the real saving from the catalog. Every company starts
 * on Free, so each card's button opens registration.
 */
function Pricing({ plans, onRegister }: { plans: BillingPlan[] | null; onRegister: () => void }) {
  const { t } = useLang();
  const [period, setPeriod] = useState<Period>("monthly");
  const savings = (plans ?? []).flatMap((plan) =>
    plan.price_monthly_nok && plan.price_annual_nok
      ? [Math.round((1 - plan.price_annual_nok / (plan.price_monthly_nok * 12)) * 100)]
      : [],
  );
  const saving = savings.length > 0 ? Math.max(...savings) : 0;

  return (
    <section className="landing-section landing-pricing" id="pricing" aria-labelledby="pricing-title">
      <SectionHead id="pricing-title" title={t("landing.pricingTitle")} lede={t("landing.pricingLede")} />
      {plans && plans.length > 0 ? (
        <>
          {saving > 0 ? (
            <div className="period-toggle" role="group" aria-label={t("landing.pricingPeriod")}>
              {(["monthly", "yearly"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={period === value ? "period-opt active" : "period-opt"}
                  aria-pressed={period === value}
                  onClick={() => setPeriod(value)}
                >
                  {value === "monthly" ? t("landing.pricingMonthly") : t("landing.pricingYearly")}
                  {value === "yearly" ? (
                    <span className="period-save">{t("landing.pricingSave", { percent: saving })}</span>
                  ) : null}
                </button>
              ))}
            </div>
          ) : null}
          <ul className="plan-cards">
            {plans.map((plan, index) => {
              const id = plan.id as "free" | "team" | "business";
              const free = plan.price_monthly_nok == null;
              const featured = id === "team";
              const yearly = period === "yearly";
              const amount = free ? 0 : yearly ? plan.price_annual_nok : plan.price_monthly_nok;
              return (
                <li key={plan.id} className={featured ? "plan-card plan-card-featured" : "plan-card"}>
                  <div className="plan-card-top">
                    <div className="plan-card-head">
                      <TierMark level={index + 1} />
                      {featured ? <span className="plan-card-tag">{t("landing.pricingRecommended")}</span> : null}
                    </div>
                    <h3>{t(`billing.plan.${id}`)}</h3>
                    <p className="plan-card-for">{t(`landing.plan.${id}.for`)}</p>
                    <p className="plan-card-price">
                      <span className="plan-card-amount">NOK {amount}</span>
                      <span className="plan-card-per">
                        {yearly ? t("landing.pricingPerYear") : t("landing.pricingPerMonth")}
                      </span>
                    </p>
                    <p className="plan-card-note">
                      {free
                        ? t("landing.pricingNoCard")
                        : yearly
                          ? t("landing.pricingBilledYearly")
                          : t("landing.pricingBilledMonthly")}
                    </p>
                    <a
                      className={featured ? "btn btn-inverse btn-block" : "btn btn-secondary btn-block"}
                      href="#signin"
                      onClick={onRegister}
                    >
                      {free ? t("landing.pricingStartFree") : t("landing.pricingStartPaid")}
                    </a>
                  </div>
                  <ul className="plan-card-features">
                    <li>
                      <IconCheck width={16} height={16} />
                      <BoldValue text={t("billing.feature.seats", { count: MARK })} value={plan.max_users} />
                    </li>
                    <li>
                      <IconCheck width={16} height={16} />
                      <BoldValue text={t("billing.feature.apps", { count: MARK })} value={plan.max_apps} />
                    </li>
                    <li>
                      <IconCheck width={16} height={16} />
                      <BoldValue
                        text={t("billing.feature.audit", { days: MARK })}
                        value={plan.audit_retention_days}
                      />
                    </li>
                  </ul>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
      <p className="pricing-included">{t("landing.pricingIncluded")}</p>
    </section>
  );
}

const MARK = "\u0000";

/** Puts the number in a translated line in bold, wherever the language places it. */
function BoldValue({ text, value }: { text: string; value: number }) {
  const [before, after = ""] = text.split(MARK);
  return (
    <span>
      {before}
      <strong>{value}</strong>
      {after}
    </span>
  );
}

/** Three rising bars, filled up to the plan's size. */
function TierMark({ level }: { level: number }) {
  return (
    <svg className="tier-mark" width="18" height="16" viewBox="0 0 18 16" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <rect
          key={i}
          x={i * 7}
          y={10 - i * 5}
          width="4"
          height={6 + i * 5}
          rx="1"
          fill="currentColor"
          opacity={i < level ? 1 : 0.22}
        />
      ))}
    </svg>
  );
}

/**
 * A form POST, so link prefetchers and crawlers never start a demo session.
 * The compact one sits in the nav.
 */
export function DemoButton({ compact = false }: { compact?: boolean }) {
  const { t } = useLang();
  return (
    <form method="post" action={demoUrl()} className="demo-form">
      <button type="submit" className={compact ? "btn btn-primary btn-nav" : "btn btn-primary"}>
        <IconPlay width={16} height={16} />
        {t("demo.cta")}
      </button>
    </form>
  );
}
