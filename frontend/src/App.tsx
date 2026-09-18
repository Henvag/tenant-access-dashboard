import { useEffect, useState } from "react";
import { getMe, listUsers, loginUrl, logoutUrl, Me, TenantUser } from "./api";
import { messageForAuthError } from "./format";
import SignupForm from "./SignupForm";
import UserTable from "./UserTable";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<TenantUser[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(() => {
    const code = new URLSearchParams(window.location.search).get("error");
    return messageForAuthError(code);
  });
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const profile = await getMe();
        if (cancelled) return;
        setMe(profile);
        if (profile.role === "admin") {
          try {
            setUsers(await listUsers());
          } catch (err) {
            setUsers([]);
            setError(err instanceof Error ? err.message : "Could not load users");
          }
        }
      } catch {
        if (!cancelled) setMe(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <main className="shell">
        <p className="muted">Loading…</p>
      </main>
    );
  }

  if (!me) {
    return (
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Access</p>
          <h1>Tenant access dashboard</h1>
          <p className="lede">
            Register your company, then sign in with Google. You only see people
            in your own tenant.
          </p>
        </header>
        {error ? <p className="banner error">{error}</p> : null}
        {notice ? <p className="banner ok">{notice}</p> : null}
        <div className="grid">
          <SignupForm
            onCreated={(domain) => {
              setError(null);
              setNotice(
                `Registered ${domain}. Sign in with Google — first user becomes admin.`
              );
            }}
          />
          <section className="panel">
            <h2>Sign in</h2>
            <p className="lede">
              Use the same Google account whose email domain you just registered
              (gmail.com for a personal Gmail).
            </p>
            <a className="button" href={loginUrl()}>
              Continue with Google
            </a>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">{me.tenant_name}</p>
          <h1>Access</h1>
        </div>
        <div className="who">
          <span>
            {me.display_name || me.email}
            <small>
              {me.role} · {me.workspace_domain}
            </small>
          </span>
          <a className="button ghost" href={logoutUrl()}>
            Sign out
          </a>
        </div>
      </header>

      {error ? <p className="banner error">{error}</p> : null}

      {me.role === "admin" ? (
        <section className="panel wide">
          <h2>People with access</h2>
          <p className="lede">
            Users who have signed into this app for @{me.workspace_domain}.
            Isolated to your tenant.
          </p>
          {users ? <UserTable users={users} /> : <p className="muted">Could not load users.</p>}
        </section>
      ) : (
        <section className="panel">
          <h2>Signed in</h2>
          <p className="lede">
            You are a member of {me.tenant_name}. Only admins can view the
            full access list.
          </p>
        </section>
      )}
    </main>
  );
}
