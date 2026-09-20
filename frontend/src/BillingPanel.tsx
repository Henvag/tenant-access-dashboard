import { useEffect, useState } from "react";
import {
  BillingPlan,
  BillingStatus,
  checkoutBilling,
  getBillingStatus,
  listBillingPlans,
  openBillingPortal,
} from "./api";
import { formatTimestamp, messageForApiError } from "./format";
import { useLang } from "./i18n";

type Props = {
  isOwner: boolean;
};

export default function BillingPanel({ isOwner }: Props) {
  const { lang, t } = useLang();
  const [plans, setPlans] = useState<BillingPlan[] | null>(null);
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [banner, setBanner] = useState<"success" | "cancel" | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const checkout = params.get("checkout");
    if (checkout === "success" || checkout === "cancel") {
      setBanner(checkout);
      params.delete("checkout");
      const next = `${window.location.pathname}?${params.toString()}`.replace(/\?$/, "");
      window.history.replaceState(null, "", next || window.location.pathname);
    }
  }, []);

  async function refresh() {
    setErrorCode(null);
    try {
      const [nextPlans, nextStatus] = await Promise.all([listBillingPlans(), getBillingStatus()]);
      setPlans(nextPlans);
      setStatus(nextStatus);
    } catch (err) {
      setErrorCode(err instanceof Error && err.message ? err.message : "load_billing");
      setPlans((current) => current ?? []);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function startCheckout(plan: "team" | "business", method: "card_monthly" | "vipps_annual") {
    setBusy(`${plan}:${method}`);
    setErrorCode(null);
    try {
      const { url } = await checkoutBilling(plan, method);
      window.location.assign(url);
    } catch (err) {
      setErrorCode(err instanceof Error && err.message ? err.message : "checkout_failed");
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    setErrorCode(null);
    try {
      const { url } = await openBillingPortal();
      window.location.assign(url);
    } catch (err) {
      setErrorCode(err instanceof Error && err.message ? err.message : "portal_failed");
      setBusy(null);
    }
  }

  const pending = !plans || !status;

  return (
    <div className="billing">
      {banner === "success" ? (
        <p className="banner ok" role="status">
          {t("billing.checkoutSuccess")}
        </p>
      ) : null}
      {banner === "cancel" ? (
        <p className="banner info" role="status">
          {t("billing.checkoutCancel")}
        </p>
      ) : null}
      {errorCode ? (
        <p className="banner error" role="alert">
          {messageForApiError(errorCode, lang)}
        </p>
      ) : null}

      <section className="panel billing-status">
        <div className="panel-head">
          <div>
            <h2>{t("billing.currentTitle")}</h2>
            <p className="hint">{t("billing.currentHint")}</p>
          </div>
          {status && isOwner && status.has_stripe_customer && status.stripe_configured ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy === "portal"}
              onClick={() => void openPortal()}
            >
              {busy === "portal" ? t("billing.working") : t("billing.manage")}
            </button>
          ) : null}
        </div>
        {pending || !status ? (
          <p className="hint">{t("billing.loading")}</p>
        ) : (
          <dl className="billing-usage">
            <div>
              <dt>{t("billing.plan")}</dt>
              <dd>{t(`billing.plan.${status.plan}` as "billing.plan.free")}</dd>
            </div>
            <div>
              <dt>{t("billing.seats")}</dt>
              <dd>
                {status.users_used} / {status.max_users}
              </dd>
            </div>
            <div>
              <dt>{t("billing.apps")}</dt>
              <dd>
                {status.apps_used} / {status.max_apps}
              </dd>
            </div>
            <div>
              <dt>{t("billing.audit")}</dt>
              <dd>{t("billing.auditDays", { days: String(status.audit_retention_days) })}</dd>
            </div>
            {status.plan_expires_at ? (
              <div>
                <dt>{t("billing.expires")}</dt>
                <dd>{formatTimestamp(status.plan_expires_at, lang)}</dd>
              </div>
            ) : null}
          </dl>
        )}
        {!isOwner ? <p className="hint">{t("billing.ownerOnly")}</p> : null}
        {status && !status.stripe_configured ? (
          <p className="hint">{t("billing.demoMode")}</p>
        ) : null}
      </section>

      <section className="billing-plans" aria-label={t("billing.plansLabel")}>
        {(plans ?? []).map((plan) => {
          const current = status?.plan === plan.id;
          const paid = plan.id === "team" || plan.id === "business";
          return (
            <article
              key={plan.id}
              className={current ? "billing-plan billing-plan-current" : "billing-plan"}
            >
              <header>
                <h3>{t(`billing.plan.${plan.id}` as "billing.plan.free")}</h3>
                {current ? <span className="billing-badge">{t("billing.current")}</span> : null}
              </header>
              <p className="billing-price">
                {plan.price_monthly_nok == null
                  ? t("billing.freePrice")
                  : t("billing.monthlyPrice", { amount: String(plan.price_monthly_nok) })}
              </p>
              {plan.price_annual_nok != null ? (
                <p className="hint">{t("billing.annualPrice", { amount: String(plan.price_annual_nok) })}</p>
              ) : null}
              <ul className="billing-features">
                <li>{t("billing.feature.seats", { count: String(plan.max_users) })}</li>
                <li>{t("billing.feature.apps", { count: String(plan.max_apps) })}</li>
                <li>{t("billing.feature.audit", { days: String(plan.audit_retention_days) })}</li>
              </ul>
              {paid && isOwner && status?.stripe_configured ? (
                <div className="billing-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy !== null || current}
                    onClick={() => void startCheckout(plan.id as "team" | "business", "card_monthly")}
                  >
                    {busy === `${plan.id}:card_monthly`
                      ? t("billing.working")
                      : t("billing.payCard")}
                  </button>
                  {status.vipps_enabled ? (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={busy !== null || current}
                      onClick={() =>
                        void startCheckout(plan.id as "team" | "business", "vipps_annual")
                      }
                    >
                      {busy === `${plan.id}:vipps_annual`
                        ? t("billing.working")
                        : t("billing.payVipps")}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
    </div>
  );
}
