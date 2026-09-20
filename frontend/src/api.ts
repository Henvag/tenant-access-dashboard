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
    throw new Error(formatDetail(data.detail) || `Request failed (${response.status})`);
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
  patch: Partial<AppInput> & { disabled?: boolean; clear_launch_url?: boolean },
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

export function getAppGrants(appId: string): Promise<string[]> {
  return request<string[]>(`/apps/${appId}/grants`);
}

export function setAppGrants(appId: string, userIds: string[]): Promise<string[]> {
  return request<string[]>(`/apps/${appId}/grants`, {
    method: "PUT",
    body: JSON.stringify({ user_ids: userIds }),
  });
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
