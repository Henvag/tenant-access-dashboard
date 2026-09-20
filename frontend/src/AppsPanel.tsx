import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AccessPolicy,
  AppInput,
  createApp,
  deleteApp,
  getAppGrants,
  issuerUrl,
  listApps,
  patchApp,
  RegisteredApp,
  rotateAppSecret,
  setAppGrants,
  TenantUser,
} from "./api";
import Avatar from "./Avatar";
import CopyButton from "./CopyButton";
import { messageForApiError } from "./format";
import { TKey, useLang } from "./i18n";
import AppMark from "./AppMark";
import { IconExternal, IconKey, IconPlus, IconSearch } from "./Icons";
import Modal from "./Modal";
import RowMenu, { MenuItem } from "./RowMenu";

type Props = {
  tenantName: string;
  users: TenantUser[] | null;
  /** Called after any change so the parent can refresh the audit feed. */
  onChanged?: () => void;
};

type Dialog =
  | { kind: "new" }
  | { kind: "edit"; app: RegisteredApp }
  | { kind: "secret"; app: RegisteredApp; secret: string; mode: "created" | "rotated" }
  | { kind: "access"; app: RegisteredApp };

const POLICY_LABEL: Record<AccessPolicy, TKey> = {
  everyone: "policy.everyone",
  admins: "policy.admins",
  assigned: "policy.assigned",
};

const POLICY_HINT: Record<AccessPolicy, TKey> = {
  everyone: "policy.everyoneHint",
  admins: "policy.adminsHint",
  assigned: "policy.assignedHint",
};

const POLICY_PILL: Record<AccessPolicy, string> = {
  everyone: "pill",
  admins: "pill pill-accent",
  assigned: "pill pill-warn",
};

function redirectTip(
  name: string,
  launchUrl: string,
  t: (key: TKey, vars?: Record<string, string | number>) => string,
): string {
  const origin = new URL(launchUrl).origin;
  if (/outline/i.test(name)) return t("apps.outlineTip", { url: origin });
  if (/grafana/i.test(name)) return t("apps.grafanaTip", { url: origin });
  return t("apps.redirectTip", { url: origin });
}

export default function AppsPanel({ tenantName, users, onChanged }: Props) {
  const { lang, t } = useLang();
  const [apps, setApps] = useState<RegisteredApp[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const issuer = issuerUrl();

  async function load() {
    try {
      setApps(await listApps());
      setError(null);
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
      setApps((current) => current ?? []);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function upsert(app: RegisteredApp) {
    setApps((current) => {
      const list = current ?? [];
      return list.some((a) => a.id === app.id)
        ? list.map((a) => (a.id === app.id ? app : a))
        : [...list, app];
    });
    onChanged?.();
  }

  async function run(appId: string, action: () => Promise<void>) {
    setBusyId(appId);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
    } finally {
      setBusyId(null);
    }
  }

  function menuFor(app: RegisteredApp): MenuItem[] {
    const items: MenuItem[] = [
      { key: "edit", label: t("apps.edit"), onSelect: () => setDialog({ kind: "edit", app }) },
    ];
    if (app.access_policy === "assigned") {
      items.push({
        key: "access",
        label: t("apps.manageAccess"),
        onSelect: () => setDialog({ kind: "access", app }),
      });
    }
    items.push({
      key: "rotate",
      label: t("apps.rotate"),
      onSelect: () => {
        if (!window.confirm(t("apps.rotateConfirm", { name: app.name }))) return;
        void run(app.id, async () => {
          const { client_secret } = await rotateAppSecret(app.id);
          setDialog({ kind: "secret", app, secret: client_secret, mode: "rotated" });
        });
      },
    });
    items.push({
      key: "toggle",
      label: app.disabled ? t("apps.enable") : t("apps.disable"),
      onSelect: () =>
        void run(app.id, async () => upsert(await patchApp(app.id, { disabled: !app.disabled }))),
    });
    items.push({
      key: "delete",
      label: t("apps.delete"),
      danger: true,
      onSelect: () => {
        if (!window.confirm(t("apps.deleteConfirm", { name: app.name }))) return;
        void run(app.id, async () => {
          await deleteApp(app.id);
          setApps((current) => (current ?? []).filter((a) => a.id !== app.id));
          onChanged?.();
        });
      },
    });
    return items;
  }

  return (
    <>
      <section className="card">
        <div className="card-head">
          <div>
            <h2>{t("apps.title")}</h2>
            <p className="hint">{t("apps.hint", { tenant: tenantName })}</p>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => setDialog({ kind: "new" })}>
            <IconPlus width={16} height={16} />
            {t("apps.new")}
          </button>
        </div>

        {error ? (
          <p className="banner error" role="alert">
            {error}
          </p>
        ) : null}

        {apps === null ? (
          <div className="skeleton-table" aria-busy="true">
            {[0, 1].map((i) => (
              <div className="skeleton-row" key={i}>
                <span className="sk sk-avatar" />
                <span className="sk sk-line w-40" />
                <span className="sk sk-line w-20" />
              </div>
            ))}
          </div>
        ) : apps.length === 0 ? (
          <div className="empty">
            <div className="empty-art" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <h3>{t("apps.emptyTitle")}</h3>
            <p>{t("apps.emptyBody")}</p>
          </div>
        ) : (
          <ul className="app-list">
            {apps.map((app) => (
              <li key={app.id} className={app.disabled ? "app-row app-disabled" : "app-row"}>
                <div className="app-row-main">
                  <AppMark name={app.name} />
                  <div className="app-row-text">
                    <div className="app-row-title">
                      <span className="name-text">{app.name}</span>
                      <span className={POLICY_PILL[app.access_policy]}>
                        {t(POLICY_LABEL[app.access_policy])}
                      </span>
                      {app.access_policy === "assigned" ? (
                        <button
                          type="button"
                          className="link link-quiet"
                          onClick={() => setDialog({ kind: "access", app })}
                        >
                          {t("apps.grants", { count: app.grant_count })}
                        </button>
                      ) : null}
                      {app.disabled ? (
                        <span className="pill pill-xs pill-danger">{t("status.disabled")}</span>
                      ) : null}
                    </div>
                    <div className="app-row-meta">
                      <span className="kv">
                        <span className="kv-label">{t("apps.clientId")}</span>
                        <code className="mono">{app.client_id}</code>
                        <CopyButton value={app.client_id} />
                      </span>
                      {app.launch_url ? (
                        <a
                          className="kv-link"
                          href={app.launch_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <IconExternal width={13} height={13} />
                          {t("apps.open")}
                        </a>
                      ) : null}
                    </div>
                  </div>
                </div>
                <RowMenu items={menuFor(app)} busy={busyId === app.id} label={t("apps.moreActions")} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>
              <IconKey width={16} height={16} className="inline-icon" />
              {t("apps.issuer")}
            </h2>
            <p className="hint">{t("apps.issuerHint")}</p>
          </div>
        </div>
        <div className="kv-grid">
          <div className="kv-row">
            <span className="kv-label">{t("apps.issuer")}</span>
            <code className="mono">{issuer}</code>
            <CopyButton value={issuer} />
          </div>
          {(
            [
              ["apps.endpoint.discovery", `${issuer}/.well-known/openid-configuration`],
              ["apps.endpoint.authorize", `${issuer}/oauth/authorize`],
              ["apps.endpoint.token", `${issuer}/oauth/token`],
              ["apps.endpoint.userinfo", `${issuer}/oauth/userinfo`],
              ["apps.endpoint.jwks", `${issuer}/.well-known/jwks.json`],
            ] as const satisfies ReadonlyArray<readonly [TKey, string]>
          ).map(([labelKey, url]) => (
            <div className="kv-row" key={labelKey}>
              <span className="kv-label">{t(labelKey)}</span>
              <code className="mono">{url}</code>
              <CopyButton value={url} />
            </div>
          ))}
        </div>
      </section>

      {dialog?.kind === "new" ? (
        <Modal
          title={t("apps.newTitle")}
          hint={t("apps.newHint", { tenant: tenantName })}
          onClose={() => setDialog(null)}
        >
          <AppForm
            tenantName={tenantName}
            onCancel={() => setDialog(null)}
            onSubmit={async (input) => {
              const created = await createApp(input);
              upsert(created);
              setDialog({ kind: "secret", app: created, secret: created.client_secret, mode: "created" });
            }}
          />
        </Modal>
      ) : null}

      {dialog?.kind === "edit" ? (
        <Modal title={t("apps.settingsFor", { name: dialog.app.name })} onClose={() => setDialog(null)}>
          <AppForm
            tenantName={tenantName}
            initial={dialog.app}
            onCancel={() => setDialog(null)}
            onSubmit={async (input) => {
              const updated = await patchApp(dialog.app.id, {
                ...input,
                clear_launch_url: input.launch_url === null,
              });
              upsert(updated);
              setDialog(null);
            }}
          />
        </Modal>
      ) : null}

      {dialog?.kind === "secret" ? (
        <Modal
          title={
            dialog.mode === "created"
              ? t("apps.created", { name: dialog.app.name })
              : t("apps.rotated", { name: dialog.app.name })
          }
          hint={t("apps.secretOnce")}
          onClose={() => setDialog(null)}
        >
          <div className="kv-grid">
            <div className="kv-row">
              <span className="kv-label">{t("apps.clientId")}</span>
              <code className="mono">{dialog.app.client_id}</code>
              <CopyButton value={dialog.app.client_id} />
            </div>
            <div className="kv-row">
              <span className="kv-label">{t("apps.clientSecret")}</span>
              <code className="mono secret">{dialog.secret}</code>
              <CopyButton value={dialog.secret} />
            </div>
            <div className="kv-row">
              <span className="kv-label">{t("apps.issuer")}</span>
              <code className="mono">{issuer}</code>
              <CopyButton value={issuer} />
            </div>
          </div>
          {dialog.app.launch_url ? (
            <p className="hint tip-box">{redirectTip(dialog.app.name, dialog.app.launch_url, t)}</p>
          ) : null}
          <div className="modal-actions">
            <button type="button" className="btn btn-primary" onClick={() => setDialog(null)}>
              {t("apps.done")}
            </button>
          </div>
        </Modal>
      ) : null}

      {dialog?.kind === "access" ? (
        <Modal
          title={t("apps.accessTitle", { name: dialog.app.name })}
          hint={t("apps.accessHint")}
          onClose={() => setDialog(null)}
          wide
        >
          <AccessEditor
            app={dialog.app}
            users={users ?? []}
            onCancel={() => setDialog(null)}
            onSaved={(count) => {
              upsert({ ...dialog.app, grant_count: count });
              setDialog(null);
            }}
          />
        </Modal>
      ) : null}
    </>
  );
}

// ---------- form ----------

function AppForm({
  tenantName,
  initial,
  onSubmit,
  onCancel,
}: {
  tenantName: string;
  initial?: RegisteredApp;
  onSubmit: (input: AppInput) => Promise<void>;
  onCancel: () => void;
}) {
  const { lang, t } = useLang();
  const [name, setName] = useState(initial?.name ?? "");
  const [redirects, setRedirects] = useState(initial?.redirect_uris.join("\n") ?? "");
  const [launchUrl, setLaunchUrl] = useState(initial?.launch_url ?? "");
  const [policy, setPolicy] = useState<AccessPolicy>(initial?.access_policy ?? "everyone");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        redirect_uris: redirects
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean),
        launch_url: launchUrl.trim() || null,
        access_policy: policy,
      });
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="app-form">
      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}
      <label className="field">
        <span>{t("apps.nameLabel")}</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Grafana"
          maxLength={120}
          required
        />
      </label>
      <label className="field">
        <span>{t("apps.redirects")}</span>
        <textarea
          value={redirects}
          onChange={(e) => setRedirects(e.target.value)}
          placeholder="https://grafana.example.com/login/generic_oauth"
          rows={3}
          required
          spellCheck={false}
        />
        <small>{t("apps.redirectsHint")}</small>
      </label>
      <label className="field">
        <span>{t("apps.launchUrl")}</span>
        <input
          value={launchUrl}
          onChange={(e) => setLaunchUrl(e.target.value)}
          placeholder="https://grafana.example.com/login/generic_oauth"
          type="url"
        />
        <small>{t("apps.launchUrlHint")}</small>
      </label>
      <fieldset className="field policy-field">
        <legend>{t("apps.policy")}</legend>
        {(["everyone", "admins", "assigned"] as AccessPolicy[]).map((value) => (
          <label key={value} className={policy === value ? "radio-card active" : "radio-card"}>
            <input
              type="radio"
              name="policy"
              value={value}
              checked={policy === value}
              onChange={() => setPolicy(value)}
            />
            <span className="radio-card-text">
              <strong>{t(POLICY_LABEL[value])}</strong>
              <small>{t(POLICY_HINT[value], { tenant: tenantName })}</small>
            </span>
          </label>
        ))}
      </fieldset>
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={pending}>
          {t("apps.cancel")}
        </button>
        <button type="submit" className="btn btn-primary" disabled={pending}>
          {initial
            ? pending
              ? t("apps.saving")
              : t("apps.save")
            : pending
              ? t("apps.creating")
              : t("apps.create")}
        </button>
      </div>
    </form>
  );
}

// ---------- access editor ----------

function AccessEditor({
  app,
  users,
  onSaved,
  onCancel,
}: {
  app: RegisteredApp;
  users: TenantUser[];
  onSaved: (count: number) => void;
  onCancel: () => void;
}) {
  const { lang, t } = useLang();
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAppGrants(app.id)
      .then((ids) => {
        if (!cancelled) setSelected(new Set(ids));
      })
      .catch((err) => {
        if (!cancelled) {
          setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
          setSelected(new Set());
        }
      });
    return () => {
      cancelled = true;
    };
  }, [app.id, lang]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return users
      .filter((u) => !u.disabled)
      .filter(
        (u) =>
          !needle ||
          u.email.toLowerCase().includes(needle) ||
          (u.display_name ?? "").toLowerCase().includes(needle),
      );
  }, [users, query]);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current ?? []);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function save() {
    if (!selected) return;
    setPending(true);
    setError(null);
    try {
      const ids = await setAppGrants(app.id, Array.from(selected));
      onSaved(ids.length);
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
      setPending(false);
    }
  }

  return (
    <div className="access-editor">
      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}
      <label className="search">
        <IconSearch />
        <input
          type="search"
          placeholder={t("search.placeholder")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <ul className="check-list" aria-busy={selected === null}>
        {visible.map((user) => {
          const checked = selected?.has(user.id) ?? false;
          return (
            <li key={user.id}>
              <label className={checked ? "check-row checked" : "check-row"}>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={selected === null}
                  onChange={() => toggle(user.id)}
                />
                <Avatar name={user.display_name} email={user.email} size="sm" />
                <span className="person-text">
                  <span className="person-name">
                    <span className="name-text">{user.display_name || user.email.split("@")[0]}</span>
                    {user.role === "admin" ? (
                      <span className="pill pill-xs pill-accent">{t("role.admin")}</span>
                    ) : null}
                  </span>
                  <span className="person-email">{user.email}</span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <div className="modal-actions">
        <span className="hint">{t("apps.grants", { count: selected?.size ?? 0 })}</span>
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={pending}>
          {t("apps.cancel")}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void save()}
          disabled={pending || selected === null}
        >
          {pending ? t("apps.saving") : t("apps.save")}
        </button>
      </div>
    </div>
  );
}
