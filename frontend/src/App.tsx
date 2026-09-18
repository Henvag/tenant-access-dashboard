import { useEffect, useState } from "react";
import { getMe, Me } from "./api";
import Dashboard from "./Dashboard";
import { messageForAuthError } from "./format";
import Landing from "./Landing";

type Session = { status: "loading" } | { status: "anonymous" } | { status: "ready"; me: Me };

function readAuthError(): { message: string | null; code: string | null } {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("error");
  if (code) {
    params.delete("error");
    const clean = `${window.location.pathname}${params.size ? `?${params}` : ""}`;
    window.history.replaceState(null, "", clean);
  }
  return { message: messageForAuthError(code), code };
}

export default function App() {
  const [session, setSession] = useState<Session>({ status: "loading" });
  const [authError] = useState(readAuthError);

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
        <p>Loading your workspace…</p>
      </div>
    );
  }

  if (session.status === "anonymous") {
    return (
      <Landing
        initialError={authError.message}
        initialTab={authError.code === "no_tenant" ? "register" : "signin"}
      />
    );
  }

  return <Dashboard me={session.me} />;
}
