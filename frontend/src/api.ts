export const API_BASE =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export type UserRole = "admin" | "user";

export type Me = {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  tenant_id: string;
  tenant_name: string;
  workspace_domain: string;
  last_login_at: string | null;
  disabled: boolean;
  is_owner: boolean;
  plan: "free" | "team" | "business";
  max_apps: number;
  max_users: number;
  audit_retention_days: number;
  has_logo: boolean;
};

export type TenantUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  last_login_at: string | null;
  disabled: boolean;
  is_owner: boolean;
};

export type Tenant = {
  id: string;
  name: string;
  workspace_domain: string;
  created_at: string;
};

type ApiErrorBody = {
  detail?: string | { msg?: string }[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = (await response.json().catch(() => ({}))) as T & ApiErrorBody;
  if (!response.ok) {
    throw new Error(formatDetail(data.detail) || `request_failed:${response.status}`);
  }
  return data;
}

function formatDetail(detail: ApiErrorBody["detail"]): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  return detail.map((item) => item.msg).filter(Boolean).join(", ");
}

export type AuditEventType =
  | "login"
  | "login_failed"
  | "user_disabled"
  | "user_enabled"
  | "role_changed"
  | "app_created"
  | "app_deleted"
  | "app_access_granted"
  | "app_access_revoked"
  | "app_login"
  | "app_login_denied";

export type AuditEvent = {
  id: string;
  email: string;
  display_name: string | null;
  event_type: AuditEventType;
  idp: "google" | "microsoft";
  error_code: string | null;
  ip_address: string | null;
  details: Record<string, string> | null;
  created_at: string;
};

export type AccessPolicy = "everyone" | "admins" | "assigned";

export type RegisteredApp = {
  id: string;
  name: string;
  client_id: string;
  redirect_uris: string[];
  launch_url: string | null;
  backchannel_logout_uri: string | null;
  access_policy: AccessPolicy;
  disabled: boolean;
  created_at: string;
  grant_count: number;
};

export type RegisteredAppWithSecret = RegisteredApp & { client_secret: string };

export type MyApp = {
  id: string;
  name: string;
  launch_url: string | null;
  access_policy: AccessPolicy;
};

export type AppInput = {
  name: string;
  redirect_uris: string[];
  launch_url: string | null;
  backchannel_logout_uri?: string | null;
  access_policy: AccessPolicy;
};

export function listApps(): Promise<RegisteredApp[]> {
  return request<RegisteredApp[]>("/apps");
}

export function listMyApps(): Promise<MyApp[]> {
  return request<MyApp[]>("/apps/mine");
}

export function createApp(input: AppInput): Promise<RegisteredAppWithSecret> {
  return request<RegisteredAppWithSecret>("/apps", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function patchApp(
  appId: string,
  patch: Partial<AppInput> & {
    disabled?: boolean;
    clear_launch_url?: boolean;
    clear_backchannel_logout_uri?: boolean;
  },
): Promise<RegisteredApp> {
  return request<RegisteredApp>(`/apps/${appId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteApp(appId: string): Promise<void> {
  return request<void>(`/apps/${appId}`, { method: "DELETE" });
}

export function rotateAppSecret(appId: string): Promise<{ client_secret: string }> {
  return request<{ client_secret: string }>(`/apps/${appId}/rotate-secret`, { method: "POST" });
}

export function getAppGrants(appId: string): Promise<AppGrants> {
  return request<AppGrants>(`/apps/${appId}/grants`);
}

export function setAppGrants(
  appId: string,
  userIds: string[],
  emails: string[] = [],
): Promise<AppGrants> {
  return request<AppGrants>(`/apps/${appId}/grants`, {
    method: "PUT",
    body: JSON.stringify({ user_ids: userIds, emails }),
  });
}

export type CompanyInvite = {
  token: string;
  url: string;
  created_at: string;
};

export type PublicInvite = {
  tenant_name: string;
  workspace_domain: string;
  has_logo: boolean;
};

export type AppGrants = {
  user_ids: string[];
  pending_emails: string[];
};

export function getCompanyInvite(): Promise<CompanyInvite | null> {
  return request<CompanyInvite | null>("/invites/company");
}

export function ensureCompanyInvite(): Promise<CompanyInvite> {
  return request<CompanyInvite>("/invites/company", { method: "POST" });
}

export function rotateCompanyInvite(): Promise<CompanyInvite> {
  return request<CompanyInvite>("/invites/company/rotate", { method: "POST" });
}

export function lookupPublicInvite(token: string): Promise<PublicInvite> {
  return request<PublicInvite>(`/public/invites/${encodeURIComponent(token)}`);
}

export function issuerUrl(): string {
  return API_BASE || window.location.origin;
}

export function getMe(): Promise<Me> {
  return request<Me>("/auth/me");
}

export function listUsers(): Promise<TenantUser[]> {
  return request<TenantUser[]>("/users");
}

export function setUserDisabled(userId: string, disabled: boolean): Promise<TenantUser> {
  return request<TenantUser>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ disabled }),
  });
}

export function setUserRole(userId: string, role: UserRole): Promise<TenantUser> {
  return request<TenantUser>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function listAuditEvents(limit = 50): Promise<AuditEvent[]> {
  return request<AuditEvent[]>(`/audit?limit=${limit}`);
}

export function createTenant(name: string, workspace_domain: string): Promise<Tenant> {
  return request<Tenant>("/tenants", {
    method: "POST",
    body: JSON.stringify({ name, workspace_domain }),
  });
}

export function loginUrl(provider: "google" | "microsoft" = "google"): string {
  return `${API_BASE}/auth/login?provider=${provider}`;
}

export function logoutUrl(): string {
  return `${API_BASE}/auth/logout`;
}

export type BillingPlan = {
  id: "free" | "team" | "business";
  max_users: number;
  max_apps: number;
  audit_retention_days: number;
  price_monthly_nok: number | null;
  price_annual_nok: number | null;
};

export type BillingStatus = {
  plan: "free" | "team" | "business";
  max_users: number;
  max_apps: number;
  audit_retention_days: number;
  users_used: number;
  apps_used: number;
  plan_expires_at: string | null;
  stripe_configured: boolean;
  vipps_enabled: boolean;
  has_stripe_customer: boolean;
  can_manage: boolean;
};

export function listBillingPlans(): Promise<BillingPlan[]> {
  return request<BillingPlan[]>("/billing/plans");
}

export function getBillingStatus(): Promise<BillingStatus> {
  return request<BillingStatus>("/billing/status");
}

export function checkoutBilling(
  plan: "team" | "business",
  method: "card_monthly" | "vipps_annual",
): Promise<{ url: string }> {
  return request<{ url: string }>("/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ plan, method }),
  });
}

export function openBillingPortal(): Promise<{ url: string }> {
  return request<{ url: string }>("/billing/portal", { method: "POST" });
}

export type TeamAgent = {
  id: string;
  name: string;
  url: string;
  position: number;
};

export function listAgents(): Promise<TeamAgent[]> {
  return request<TeamAgent[]>("/agents");
}

export function createAgent(name: string, url: string): Promise<TeamAgent> {
  return request<TeamAgent>("/agents", {
    method: "POST",
    body: JSON.stringify({ name, url }),
  });
}

export function deleteAgent(id: string): Promise<void> {
  return request<void>(`/agents/${id}`, { method: "DELETE" });
}

export async function uploadCompanyLogo(file: File): Promise<void> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_BASE}/company/logo`, {
    method: "PUT",
    credentials: "include",
    body,
  });
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(typeof data.detail === "string" ? data.detail : `request_failed:${response.status}`);
  }
}

export function clearCompanyLogo(): Promise<void> {
  return request<void>("/company/logo", { method: "DELETE" });
}

export async function fetchCompanyLogo(): Promise<string | null> {
  const response = await fetch(`${API_BASE}/company/logo`, { credentials: "include" });
  if (!response.ok) return null;
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
