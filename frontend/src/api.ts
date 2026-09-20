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
};

export type TenantUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  last_login_at: string | null;
  disabled: boolean;
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

export type AuditEvent = {
  id: string;
  email: string;
  display_name: string | null;
  event_type: "login" | "login_failed" | "user_disabled" | "user_enabled";
  idp: "google" | "microsoft";
  error_code: string | null;
  ip_address: string | null;
  created_at: string;
};

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
