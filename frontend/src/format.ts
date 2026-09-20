import { Lang, LOCALES, TKey, translate } from "./i18n";

const AUTH_ERROR_KEYS: Record<string, TKey> = {
  no_tenant: "auth.no_tenant",
  invalid_domain: "auth.invalid_domain",
  domain_mismatch: "auth.domain_mismatch",
  missing_claims: "auth.missing_claims",
  unverified_email: "auth.unverified_email",
  identity_conflict: "auth.identity_conflict",
  user_disabled: "auth.user_disabled",
  seat_limit_reached: "auth.seat_limit_reached",
  oidc_failed: "auth.oidc_failed",
  app_unknown_client: "auth.app_unknown_client",
  app_invalid_redirect: "auth.app_invalid_redirect",
  invite_not_found: "error.invite_not_found",
};

const DENIAL_KEYS: Record<string, TKey> = {
  not_assigned: "denied.not_assigned",
  admins_only: "denied.admins_only",
  user_disabled: "denied.user_disabled",
  wrong_tenant: "denied.wrong_tenant",
  app_disabled: "denied.app_disabled",
};

/** Result of an app sign-in attempt that was refused at /oauth/authorize. */
export type AppDenial = { app: string; reason: string | null };

export function messageForAppDenial(denial: AppDenial, lang: Lang): string {
  const head = translate(lang, "auth.app_access_denied", { app: denial.app });
  const key = denial.reason ? DENIAL_KEYS[denial.reason] : undefined;
  return key ? `${head} ${translate(lang, key)}` : head;
}

const API_ERROR_KEYS: Record<string, TKey> = {
  tenant_exists: "error.tenant_exists",
  name_required: "error.name_required",
  domain_url: "error.domain_url",
  domain_invalid: "error.domain_invalid",
  not_signed_in: "error.not_signed_in",
  admin_required: "error.admin_required",
  user_not_found: "error.user_not_found",
  cannot_disable_self: "error.cannot_disable_self",
  cannot_disable_last_admin: "error.cannot_disable_last_admin",
  user_disabled: "error.user_disabled",
  cannot_disable_owner: "error.cannot_disable_owner",
  cannot_disable_admin: "error.cannot_disable_admin",
  owner_required: "error.owner_required",
  cannot_change_own_role: "error.cannot_change_own_role",
  cannot_change_owner_role: "error.cannot_change_owner_role",
  cannot_demote_last_admin: "error.cannot_demote_last_admin",
  load_people: "error.load_people",
  app_not_found: "error.app_not_found",
  app_limit_reached: "error.app_limit_reached",
  seat_limit_reached: "error.seat_limit_reached",
  stripe_unconfigured: "error.stripe_unconfigured",
  vipps_unconfigured: "error.vipps_unconfigured",
  stripe_price_unconfigured: "error.stripe_price_unconfigured",
  no_stripe_customer: "error.no_stripe_customer",
  load_billing: "error.load_billing",
  checkout_failed: "error.checkout_failed",
  portal_failed: "error.portal_failed",
  invalid_email: "error.invalid_email",
  email_domain_mismatch: "error.email_domain_mismatch",
  invite_not_found: "error.invite_not_found",
  tenant_missing: "error.tenant_missing",
  ...AUTH_ERROR_KEYS,
};

export function messageForAuthError(code: string | null, lang: Lang): string | null {
  if (!code) return null;
  const key = AUTH_ERROR_KEYS[code];
  return key ? translate(lang, key) : translate(lang, "auth.generic", { code });
}

export function messageForApiError(codeOrMessage: string, lang: Lang): string {
  const key = API_ERROR_KEYS[codeOrMessage];
  if (key) return translate(lang, key);
  const failed = codeOrMessage.match(/^request_failed:(\d+)$/);
  if (failed) {
    return translate(lang, "error.request_failed", { status: failed[1] });
  }
  // Pydantic may return "Value error, domain_invalid"
  const match = codeOrMessage.match(/\b(tenant_exists|name_required|domain_url|domain_invalid)\b/);
  if (match) {
    const mapped = API_ERROR_KEYS[match[1]];
    if (mapped) return translate(lang, mapped);
  }
  return codeOrMessage || translate(lang, "error.generic");
}

export function formatTimestamp(value: string | null, lang: Lang): string {
  if (!value) return translate(lang, "time.never");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return translate(lang, "time.unknown");
  return date.toLocaleString(LOCALES[lang], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function relativeTime(value: string | null, lang: Lang, now: number = Date.now()): string {
  if (!value) return translate(lang, "time.never");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return translate(lang, "time.unknown");

  const locale = LOCALES[lang];
  const diffSeconds = Math.round((date.getTime() - now) / 1000);
  const abs = Math.abs(diffSeconds);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  if (abs < 45) return translate(lang, "time.justNow");
  if (abs < 3600) return rtf.format(Math.round(diffSeconds / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSeconds / 3600), "hour");
  if (abs < 86400 * 7) return rtf.format(Math.round(diffSeconds / 86400), "day");
  if (abs < 86400 * 30) return rtf.format(Math.round(diffSeconds / (86400 * 7)), "week");
  return date.toLocaleDateString(locale, { dateStyle: "medium" });
}

export function isWithinDays(value: string | null, days: number, now: number = Date.now()): boolean {
  if (!value) return false;
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return false;
  return now - time <= days * 86400 * 1000;
}

export function initials(name: string | null, email: string): string {
  const source = (name ?? "").trim();
  if (source) {
    const parts = source.split(/\s+/).filter(Boolean);
    const first = parts[0]?.[0] ?? "";
    const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? "" : "";
    return (first + last).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}
