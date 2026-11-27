import { useEffect, useState } from "react";
import { getMe, Me } from "./api";
import BrandMark from "./BrandMark";
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
  /** Company invite token from ?invite= (shareable onboarding link). */
  inviteToken: string | null;
};

function readEntryState(): EntryState {
  const params = new URLSearchParams(window.location.search);
  const errorCode = params.get("error");
  const app = params.get("app");
  const reason = params.get("reason");
  const continueApp = params.get("continue");
  const inviteToken = params.get("invite");

  for (const key of ["error", "app", "reason", "continue", "invite", "_"]) params.delete(key);
  // Keep the hash so a link such as tenantaccess.me/#pricing still lands on its section.
  const clean = `${window.location.pathname}${params.size ? `?${params}` : ""}${window.location.hash}`;
  window.history.replaceState(null, "", clean);

  return {
    errorCode: errorCode === "app_access_denied" ? null : errorCode,
    denial: errorCode === "app_access_denied" && app ? { app, reason } : null,
    continueApp,
    inviteToken,
  };
}

// Read once at module load: the function mutates the URL, so it must not run twice
// (React StrictMode double-invokes state initialisers in development).
export const ENTRY: EntryState = readEntryState();

export function hasEntryState(entry: EntryState = ENTRY): boolean {
  return Boolean(entry.errorCode || entry.denial || entry.continueApp || entry.inviteToken);
}

/**
 * Remembered while this browser has a session, so a returning user sees the loading
 * screen rather than the front page while /auth/me answers. Everyone else gets the front
 * page at once (it is already in the prerendered HTML) instead of waiting on the server.
 */
const SIGNED_IN_KEY = "tenant-access.signed-in";

export function rememberedSignedIn(): boolean {
  try {
    return window.localStorage.getItem(SIGNED_IN_KEY) === "1";
  } catch {
    return false;
  }
}

function rememberSignedIn(value: boolean) {
  try {
    if (value) window.localStorage.setItem(SIGNED_IN_KEY, "1");
    else window.localStorage.removeItem(SIGNED_IN_KEY);
  } catch {
    // ignore storage errors (private mode etc.)
  }
}

export default function App() {
  const { t } = useLang();
  const [session, setSession] = useState<Session>({ status: "loading" });
  const entry = ENTRY;
  // Decided once: switching from the front page to a splash midway would flicker.
  const [showLandingWhileLoading] = useState(() => !rememberedSignedIn() && !entry.continueApp);

  useEffect(() => {
    let cancelled = false;

    function loadSession() {
      getMe()
        .then((me) => {
          rememberSignedIn(true);
          if (!cancelled) setSession({ status: "ready", me });
        })
        .catch(() => {
          rememberSignedIn(false);
          if (!cancelled) setSession({ status: "anonymous" });
        });
    }

    loadSession();

    // Restoring the pre-login document keeps its old script, which does not
    // have the current nav. Reload so the tabs come from the current build.
    function onPageShow(event: PageTransitionEvent) {
      if (event.persisted) window.location.reload();
    }

    window.addEventListener("pageshow", onPageShow);
    return () => {
      cancelled = true;
      window.removeEventListener("pageshow", onPageShow);
    };
  }, []);

  if (session.status === "anonymous" || (session.status === "loading" && showLandingWhileLoading)) {
    return (
      <Landing
        initialErrorCode={entry.errorCode}
        denial={entry.denial}
        continueApp={entry.continueApp}
        inviteToken={entry.inviteToken}
        initialTab={entry.errorCode === "no_tenant" ? "register" : "signin"}
      />
    );
  }

  if (session.status === "loading") {
    return (
      <div className="splash" aria-busy="true">
        <BrandMark size={40} />
        <p>{t("app.loading")}</p>
      </div>
    );
  }

  // Parked app SSO: authorize redirected here with ?continue= while a login
  // session already exists (or was established). Resume instead of dumping
  // the user on the dashboard and dropping the RP redirect.
  if (entry.continueApp) {
    window.location.replace("/oauth/resume");
    return (
      <div className="splash" aria-busy="true">
        <BrandMark size={40} />
        <p>{t("landing.continue", { app: entry.continueApp })}</p>
      </div>
    );
  }

  return (
    <Dashboard me={session.me} denial={entry.denial} entryError={entry.errorCode} />
  );
}
