import { useEffect, useMemo, useState } from "react";
import { AuditEvent, listAuditEvents, listUsers, logoutUrl, Me, TenantUser } from "./api";
import AuditTable from "./AuditTable";
import Avatar from "./Avatar";
import { formatTimestamp, isWithinDays, messageForApiError } from "./format";
import { useLang } from "./i18n";
import {
  IconActivity,
  IconGrid,
  IconList,
  IconLogout,
  IconRefresh,
  IconSearch,
  IconShield,
  IconUsers,
} from "./Icons";
import LanguageToggle from "./LanguageToggle";
import StatCard from "./StatCard";
import UserTable from "./UserTable";

type View = "overview" | "people" | "audit";
type RoleFilter = "all" | "admin" | "user";

type Props = {
  me: Me;
};

export default function Dashboard({ me }: Props) {
  const { lang, t } = useLang();
  const isAdmin = me.role === "admin";
  const [view, setView] = useState<View>("overview");
  const [users, setUsers] = useState<TenantUser[] | null>(null);
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(isAdmin);
  const [loadingAudit, setLoadingAudit] = useState(isAdmin);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");

  // Prefer the people list for ownership: /auth/me can be stale if the page
  // was opened before the owner migration and only People was refreshed.
  const actorIsOwner =
    Boolean(me.is_owner) ||
    Boolean(users?.some((u) => u.id === me.id && u.is_owner));

  async function refresh() {
    if (!isAdmin) return;
    setLoadingUsers(true);
    setLoadingAudit(true);
    setErrorCode(null);
    try {
      const [nextUsers, nextEvents] = await Promise.all([listUsers(), listAuditEvents(50)]);
      setUsers(nextUsers);
      setEvents(nextEvents);
    } catch (err) {
      setErrorCode(err instanceof Error && err.message ? err.message : "load_people");
      setUsers((current) => current ?? []);
      setEvents((current) => current ?? []);
    } finally {
      setLoadingUsers(false);
      setLoadingAudit(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const stats = useMemo(() => {
    const list = users ?? [];
    return {
      total: list.length,
      admins: list.filter((u) => u.role === "admin").length,
      members: list.filter((u) => u.role === "user").length,
      activeWeek: list.filter((u) => isWithinDays(u.last_login_at, 7)).length,
    };
  }, [users]);

  const recentEvents = useMemo(() => (events ?? []).slice(0, 5), [events]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (users ?? []).filter((u) => {
      if (roleFilter !== "all" && u.role !== roleFilter) return false;
      if (!needle) return true;
      return (
        u.email.toLowerCase().includes(needle) ||
        (u.display_name ?? "").toLowerCase().includes(needle)
      );
    });
  }, [users, query, roleFilter]);

  const pendingPeople = loadingUsers && !users;
  const pendingAudit = loadingAudit && !events;
  const isFiltering = query.trim() !== "" || roleFilter !== "all";
  const loading = loadingUsers || loadingAudit;

  const title =
    view === "overview" ? t("nav.overview") : view === "people" ? t("nav.people") : t("nav.audit");

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{t("brand")}</span>
        </div>

        <div className="tenant-chip">
          <span className="tenant-chip-label">{t("sidebar.tenant")}</span>
          <strong>{me.tenant_name}</strong>
          <span className="tenant-chip-domain">@{me.workspace_domain}</span>
        </div>

        <nav className="nav" aria-label={t("nav.label")}>
          <button
            type="button"
            className={view === "overview" ? "nav-item active" : "nav-item"}
            onClick={() => setView("overview")}
          >
            <IconGrid />
            {t("nav.overview")}
          </button>
          {isAdmin ? (
            <>
              <button
                type="button"
                className={view === "people" ? "nav-item active" : "nav-item"}
                onClick={() => setView("people")}
              >
                <IconUsers />
                {t("nav.people")}
                {users ? <span className="nav-count">{users.length}</span> : null}
              </button>
              <button
                type="button"
                className={view === "audit" ? "nav-item active" : "nav-item"}
                onClick={() => setView("audit")}
              >
                <IconList />
                {t("nav.audit")}
                {events ? <span className="nav-count">{events.length}</span> : null}
              </button>
            </>
          ) : null}
        </nav>

        <div className="sidebar-foot">
          <div className="me">
            <Avatar name={me.display_name} email={me.email} />
            <div className="me-text">
              <span className="me-name">{me.display_name || me.email}</span>
              <span className="me-role">
                {actorIsOwner ? (
                  <IconShield width={12} height={12} className="me-role-icon" />
                ) : null}
                {isAdmin ? t("role.admin") : t("role.member")}
                {actorIsOwner ? (
                  <span className="me-owner-hint">{t("role.ownerLabel")}</span>
                ) : null}
              </span>
            </div>
          </div>
          <div className="sidebar-actions">
            <LanguageToggle variant="dark" />
            <a className="btn btn-ghost" href={logoutUrl()}>
              <IconLogout />
              {t("signout")}
            </a>
          </div>
        </div>
      </aside>

      <main className="content">
        <header className="content-head">
          <div>
            <p className="crumb">{me.tenant_name}</p>
            <h1>{title}</h1>
          </div>
          {isAdmin ? (
            <div className="head-actions">
              {view === "people" ? (
                <label className="search">
                  <IconSearch />
                  <input
                    type="search"
                    placeholder={t("search.placeholder")}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
              ) : null}
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void refresh()}
                disabled={loading}
                title={t("refresh")}
              >
                <IconRefresh className={loading ? "spin" : undefined} />
                <span className="sr-only">{t("refresh")}</span>
              </button>
            </div>
          ) : null}
        </header>

        {errorCode ? (
          <p className="banner error" role="alert">
            {messageForApiError(errorCode, lang)}
          </p>
        ) : null}

        {!isAdmin ? (
          <section className="card">
            <div className="card-head">
              <h2>{t("member.title")}</h2>
            </div>
            <div className="member-view">
              <Avatar name={me.display_name} email={me.email} size="lg" />
              <div>
                <strong>{me.display_name || me.email}</strong>
                <p className="hint">{me.email}</p>
                <p className="hint">
                  {t("member.body", {
                    tenant: me.tenant_name,
                    time: formatTimestamp(me.last_login_at, lang),
                  })}
                </p>
              </div>
            </div>
          </section>
        ) : view === "overview" ? (
          <>
            <section className="stats">
              <StatCard
                label={t("stats.people")}
                value={pendingPeople ? "—" : stats.total}
                hint={t("stats.peopleHint")}
                icon={<IconUsers />}
                tone="accent"
              />
              <StatCard
                label={t("stats.admins")}
                value={pendingPeople ? "—" : stats.admins}
                hint={t("stats.adminsHint")}
                icon={<IconShield />}
              />
              <StatCard
                label={t("stats.members")}
                value={pendingPeople ? "—" : stats.members}
                hint={t("stats.membersHint")}
                icon={<IconGrid />}
              />
              <StatCard
                label={t("stats.active")}
                value={pendingPeople ? "—" : stats.activeWeek}
                hint={t("stats.activeHint")}
                icon={<IconActivity />}
                tone="warm"
              />
            </section>

            <section className="card">
              <div className="card-head">
                <div>
                  <h2>{t("recent.title")}</h2>
                  <p className="hint">{t("recent.hint", { domain: me.workspace_domain })}</p>
                </div>
                <button type="button" className="link" onClick={() => setView("audit")}>
                  {t("recent.viewAll")}
                </button>
              </div>
              {pendingAudit ? (
                <TableSkeleton rows={3} />
              ) : (
                <AuditTable
                  events={recentEvents}
                  compact
                  emptyTitle={t("recent.emptyTitle")}
                  emptyBody={t("recent.emptyBody")}
                />
              )}
            </section>
          </>
        ) : view === "people" ? (
          <section className="card">
            <div className="card-head">
              <div>
                <h2>{t("people.title", { tenant: me.tenant_name })}</h2>
                <p className="hint">
                  {t("people.count", { shown: filtered.length, total: stats.total })}
                </p>
              </div>
              <div className="segmented" role="group" aria-label={t("filter.label")}>
                {(
                  [
                    ["all", t("filter.all")],
                    ["admin", t("filter.admins")],
                    ["user", t("filter.members")],
                  ] as [RoleFilter, string][]
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={roleFilter === value ? "seg active" : "seg"}
                    onClick={() => setRoleFilter(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {pendingPeople ? (
              <TableSkeleton rows={5} />
            ) : (
              <UserTable
                users={filtered}
                currentUserId={me.id}
                actorIsOwner={actorIsOwner}
                canManage={isAdmin}
                onUserUpdated={(updated) => {
                  setUsers((current) =>
                    (current ?? []).map((u) => (u.id === updated.id ? updated : u)),
                  );
                  void listAuditEvents(50).then(setEvents).catch(() => undefined);
                }}
                emptyTitle={isFiltering ? t("people.noMatches") : t("people.emptyTitle")}
                emptyBody={isFiltering ? t("people.noMatchesBody") : t("people.emptyBody")}
              />
            )}
          </section>
        ) : (
          <section className="card">
            <div className="card-head">
              <div>
                <h2>{t("audit.title")}</h2>
                <p className="hint">{t("audit.hint", { count: events?.length ?? 0 })}</p>
              </div>
            </div>
            {pendingAudit ? (
              <TableSkeleton rows={5} />
            ) : (
              <AuditTable
                events={events ?? []}
                emptyTitle={t("audit.emptyTitle")}
                emptyBody={t("audit.emptyBody")}
              />
            )}
          </section>
        )}
      </main>
    </div>
  );
}

function TableSkeleton({ rows }: { rows: number }) {
  return (
    <div className="skeleton-table" aria-busy="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div className="skeleton-row" key={index}>
          <span className="sk sk-avatar" />
          <span className="sk sk-line w-40" />
          <span className="sk sk-line w-15" />
          <span className="sk sk-line w-20" />
        </div>
      ))}
    </div>
  );
}
