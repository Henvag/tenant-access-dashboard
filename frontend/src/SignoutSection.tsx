import { FormEvent, useState } from "react";
import { clearAppSignout, RegisteredApp, setAppSignout, SignoutKind } from "./api";
import { messageForApiError } from "./format";
import { TKey, useLang } from "./i18n";

const KINDS: { value: SignoutKind; label: string; match: RegExp }[] = [
  { value: "grafana", label: "Grafana", match: /grafana/i },
  { value: "outline", label: "Outline", match: /outline/i },
  { value: "gitea", label: "Gitea", match: /gitea|forgejo/i },
];

const KEY_HINT: Record<SignoutKind, TKey> = {
  grafana: "signout.keyHint.grafana",
  outline: "signout.keyHint.outline",
  gitea: "signout.keyHint.gitea",
};

function originOf(url: string | null): string {
  if (!url) return "";
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

/** Admin key for apps that ignore back-channel logout (Grafana, Outline, Gitea). */
export default function SignoutSection({
  app,
  onUpdated,
}: {
  app: RegisteredApp;
  onUpdated: (app: RegisteredApp) => void;
}) {
  const { lang, t } = useLang();
  const guess = KINDS.find((k) => k.match.test(app.name))?.value ?? "grafana";
  const [kind, setKind] = useState<SignoutKind>(guess);
  const [baseUrl, setBaseUrl] = useState(originOf(app.launch_url ?? app.redirect_uris[0] ?? null));
  const [secret, setSecret] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<RegisteredApp>) {
    setPending(true);
    setError(null);
    try {
      onUpdated(await action());
      setSecret("");
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
    } finally {
      setPending(false);
    }
  }

  function connect(event: FormEvent) {
    event.preventDefault();
    void run(() => setAppSignout(app.id, { kind, base_url: baseUrl.trim(), secret: secret.trim() }));
  }

  const connectedLabel = KINDS.find((k) => k.value === app.signout_kind)?.label;

  return (
    <section className="signout-section">
      <h3>{t("signout.title")}</h3>
      <p className="hint">{t("signout.hint")}</p>
      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}
      {app.signout_kind ? (
        <div className="signout-connected">
          <div>
            <strong>
              {t("signout.connected", {
                kind: connectedLabel ?? app.signout_kind,
                url: app.signout_base_url ?? "",
              })}
            </strong>
            {app.signout_key_hint ? (
              <p className="hint">
                {t(app.signout_kind === "grafana" ? "signout.adminUser" : "signout.keyEnding", {
                  hint: app.signout_key_hint,
                })}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={pending}
            onClick={() => void run(() => clearAppSignout(app.id))}
          >
            {t("signout.remove")}
          </button>
        </div>
      ) : (
        <form onSubmit={connect} className="app-form">
          <label className="field">
            <span>{t("signout.kind")}</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as SignoutKind)}>
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("signout.baseUrl")}</span>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://grafana.example.com"
              type="url"
              required
            />
          </label>
          <label className="field">
            <span>{t("signout.key")}</span>
            <input
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              type="password"
              autoComplete="off"
              placeholder={kind === "grafana" ? "admin:password" : ""}
              required
            />
            <small>{t(KEY_HINT[kind])}</small>
          </label>
          <div className="modal-actions">
            <button type="submit" className="btn btn-primary" disabled={pending}>
              {pending ? t("signout.checking") : t("signout.connect")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
