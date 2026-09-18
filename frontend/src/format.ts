const AUTH_ERRORS: Record<string, string> = {
  no_tenant: "No company is registered for your email domain. Sign up first with that domain (for Gmail, use gmail.com).",
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
