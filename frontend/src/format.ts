const AUTH_ERRORS: Record<string, string> = {
  no_tenant:
    "No company is registered for your email domain yet. Register it first, then sign in.",
  invalid_domain: "That email domain is not valid.",
  domain_mismatch: "Your Google account domain does not match this Workspace.",
  missing_claims: "Google did not return a verified email. Try again.",
  unverified_email: "Your Google email is not verified.",
  identity_conflict: "This email is already linked to a different Google account.",
  oidc_failed: "Google sign-in failed. Try again.",
};

export function messageForAuthError(code: string | null): string | null {
  if (!code) return null;
  return AUTH_ERRORS[code] ?? `Sign-in error: ${code}`;
}

export function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function relativeTime(value: string | null, now: number = Date.now()): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";

  const diffSeconds = Math.round((date.getTime() - now) / 1000);
  const abs = Math.abs(diffSeconds);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  if (abs < 45) return "Just now";
  if (abs < 3600) return rtf.format(Math.round(diffSeconds / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSeconds / 3600), "hour");
  if (abs < 86400 * 7) return rtf.format(Math.round(diffSeconds / 86400), "day");
  if (abs < 86400 * 30) return rtf.format(Math.round(diffSeconds / (86400 * 7)), "week");
  return date.toLocaleDateString(undefined, { dateStyle: "medium" });
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
