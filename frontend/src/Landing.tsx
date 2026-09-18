import { useState } from "react";
import { loginUrl } from "./api";
import { IconGlobe, IconGoogle, IconLock, IconShield } from "./Icons";
import SignupForm from "./SignupForm";

type Tab = "signin" | "register";

type Props = {
  initialError: string | null;
  initialTab: Tab;
};

export default function Landing({ initialError, initialTab }: Props) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [error, setError] = useState<string | null>(initialError);
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <main className="landing">
      <section className="landing-intro">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">Tenant Access</span>
        </div>

        <h1>See who has access to your company, in one place.</h1>
        <p className="landing-lede">
          Register your company, let employees sign in with Google, and give admins a clear
          view of everyone in the tenant. Each company's data is isolated at the database
          level.
        </p>

        <ul className="feature-list">
          <li>
            <span className="feature-icon">
              <IconGoogle width={16} height={16} />
            </span>
            <div>
              <strong>Google sign-in</strong>
              <span>OpenID Connect. No passwords to manage.</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">
              <IconShield />
            </span>
            <div>
              <strong>Isolated per tenant</strong>
              <span>Postgres row-level security keeps companies apart.</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">
              <IconLock />
            </span>
            <div>
              <strong>Admin and member roles</strong>
              <span>The first person from a domain becomes admin.</span>
            </div>
          </li>
        </ul>
      </section>

      <section className="landing-card">
        <div className="tabs" role="tablist" aria-label="Get started">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "signin"}
            className={tab === "signin" ? "tab active" : "tab"}
            onClick={() => setTab("signin")}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "register"}
            className={tab === "register" ? "tab active" : "tab"}
            onClick={() => setTab("register")}
          >
            Register company
          </button>
        </div>

        {error ? (
          <p className="banner error" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="banner ok" role="status">
            {notice}
          </p>
        ) : null}

        {tab === "signin" ? (
          <div className="tab-panel">
            <h2>Welcome back</h2>
            <p className="hint">
              Use the Google account on your company's registered email domain.
            </p>
            <a className="btn btn-google btn-block" href={loginUrl()}>
              <IconGoogle />
              Continue with Google
            </a>
            <p className="fineprint">
              <IconGlobe width={14} height={14} />
              New company?{" "}
              <button type="button" className="link" onClick={() => setTab("register")}>
                Register it first
              </button>
              .
            </p>
          </div>
        ) : (
          <div className="tab-panel">
            <h2>Register your company</h2>
            <p className="hint">Takes ten seconds. Then sign in with Google to become admin.</p>
            <SignupForm
              onCreated={(domain) => {
                setError(null);
                setNotice(`${domain} is registered. Sign in with a @${domain} Google account.`);
                setTab("signin");
              }}
            />
          </div>
        )}
      </section>
    </main>
  );
}
