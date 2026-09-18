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
};

export type TenantUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  last_login_at: string | null;
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

export function getMe(): Promise<Me> {
  return request<Me>("/auth/me");
}

export function listUsers(): Promise<TenantUser[]> {
  return request<TenantUser[]>("/users");
}

export function createTenant(name: string, workspace_domain: string): Promise<Tenant> {
  return request<Tenant>("/tenants", {
    method: "POST",
    body: JSON.stringify({ name, workspace_domain }),
  });
}

export function loginUrl(): string {
  return `${API_BASE}/auth/login`;
}

export function logoutUrl(): string {
  return `${API_BASE}/auth/logout`;
}
