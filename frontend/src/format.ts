import { Lang, LOCALES, TKey, translate } from "./i18n";

const AUTH_ERROR_KEYS: Record<string, TKey> = {
  no_tenant: "auth.no_tenant",
  invalid_domain: "auth.invalid_domain",
  domain_mismatch: "auth.domain_mismatch",
  missing_claims: "auth.missing_claims",
  unverified_email: "auth.unverified_email",
  identity_conflict: "auth.identity_conflict",
  oidc_failed: "auth.oidc_failed",
};

export function messageForAuthError(code: string | null, lang: Lang): string | null {
  if (!code) return null;
  const key = AUTH_ERROR_KEYS[code];
  return key ? translate(lang, key) : translate(lang, "auth.generic", { code });
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
