import { useEffect, useState } from "react";
import { getMe, Me } from "./api";
import Dashboard from "./Dashboard";
import { AppDenial } from "./format";
import { useLang } from "./i18n";
import Landing from "./Landing";

type Session = { status: "loading" } | { status: "anonymous" } | { status: "ready"; me: Me };

/** One-shot flags the backend passes back via the URL after a redirect. */
export type EntryState = {
  errorCode: string | null;
  /** App sign-in refused at /oauth/authorize. */
  denial: AppDenial | null;
  /** An app is waiting for the user to sign in (parked authorize request). */
  continueApp: string | null;
};

function readEntryState(): EntryState {
  const params = new URLSearchParams(window.location.search);
  const errorCode = params.get("error");
  const app = params.get("app");
  const reason = params.get("reason");
  const continueApp = params.get("continue");

  for (const key of ["error", "app", "reason", "continue"]) params.delete(key);
  const clean = `${window.location.pathname}${params.size ? `?${params}` : ""}`;
  window.history.replaceState(null, "", clean);

  return {
    errorCode: errorCode === "app_access_denied" ? null : errorCode,
    denial: errorCode === "app_access_denied" && app ? { app, reason } : null,
    continueApp,
  };
}

// Read once at module load: the function mutates the URL, so it must not run twice
// (React StrictMode double-invokes state initialisers in development).
const ENTRY: EntryState = readEntryState();

export default function App() {
  const { t } = useLang();
  const [session, setSession] = useState<Session>({ status: "loading" });
  const entry = ENTRY;

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (!cancelled) setSession({ status: "ready", me });
      })
      .catch(() => {
        if (!cancelled) setSession({ status: "anonymous" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (session.status === "loading") {
    return (
      <div className="splash" aria-busy="true">
        <span className="brand-mark" aria-hidden="true" />
        <p>{t("app.loading")}</p>
      </div>
    );
  }

  if (session.status === "anonymous") {
    return (
      <Landing
        initialErrorCode={entry.errorCode}
        denial={entry.denial}
        continueApp={entry.continueApp}
        initialTab={entry.errorCode === "no_tenant" ? "register" : "signin"}
      />
    );
  }

  // Parked app SSO: authorize redirected here with ?continue= while a login
  // session already exists (or was established). Resume instead of dumping
  // the user on the dashboard and dropping the RP redirect.
  if (entry.continueApp) {
    window.location.replace("/oauth/resume");
    return (
      <div className="splash" aria-busy="true">
        <span className="brand-mark" aria-hidden="true" />
        <p>{t("landing.continue", { app: entry.continueApp })}</p>
      </div>
    );
  }

  return (
    <Dashboard me={session.me} denial={entry.denial} entryError={entry.errorCode} />
  );
}
