import { useEffect, useMemo, useState } from "react";
import { listUsers, logoutUrl, Me, TenantUser } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, isWithinDays } from "./format";
import {
  IconActivity,
  IconGrid,
  IconLogout,
  IconRefresh,
  IconSearch,
  IconShield,
  IconUsers,
} from "./Icons";
import StatCard from "./StatCard";
import UserTable from "./UserTable";

type View = "overview" | "people";
type RoleFilter = "all" | "admin" | "user";

type Props = {
  me: Me;
};

export default function Dashboard({ me }: Props) {
  const isAdmin = me.role === "admin";
  const [view, setView] = useState<View>("overview");
  const [users, setUsers] = useState<TenantUser[] | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(isAdmin);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");

  async function refresh() {
    if (!isAdmin) return;
    setLoadingUsers(true);
    setError(null);
    try {
      setUsers(await listUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load people");
      setUsers((current) => current ?? []);
    } finally {
      setLoadingUsers(false);
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

  const recent = useMemo(() => {
    return [...(users ?? [])]
      .filter((u) => u.last_login_at)
      .sort((a, b) => (b.last_login_at ?? "").localeCompare(a.last_login_at ?? ""))
      .slice(0, 5);
  }, [users]);

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

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">Tenant Access</span>
        </div>

        <div className="tenant-chip">
          <span className="tenant-chip-label">Tenant</span>
          <strong>{me.tenant_name}</strong>
          <span className="tenant-chip-domain">@{me.workspace_domain}</span>
        </div>

        <nav className="nav" aria-label="Main">
          <button
            type="button"
            className={view === "overview" ? "nav-item active" : "nav-item"}
            onClick={() => setView("overview")}
          >
            <IconGrid />
            Overview
          </button>
          {isAdmin ? (
            <button
              type="button"
              className={view === "people" ? "nav-item active" : "nav-item"}
              onClick={() => setView("people")}
            >
              <IconUsers />
              People
              {users ? <span className="nav-count">{users.length}</span> : null}
            </button>
          ) : null}
        </nav>

        <div className="sidebar-foot">
          <div className="me">
            <Avatar name={me.display_name} email={me.email} />
            <div className="me-text">
              <span className="me-name">{me.display_name || me.email}</span>
              <span className="me-role">{isAdmin ? "Admin" : "Member"}</span>
            </div>
          </div>
          <a className="btn btn-ghost btn-block" href={logoutUrl()}>
            <IconLogout />
            Sign out
          </a>
        </div>
      </aside>

      <main className="content">
        <header className="content-head">
          <div>
            <p className="crumb">{me.tenant_name}</p>
            <h1>{view === "overview" ? "Overview" : "People"}</h1>
          </div>
          {isAdmin ? (
            <div className="head-actions">
              {view === "people" ? (
                <label className="search">
                  <IconSearch />
                  <input
                    type="search"
                    placeholder="Search name or email"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
              ) : null}
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void refresh()}
                disabled={loadingUsers}
                title="Refresh"
              >
                <IconRefresh className={loadingUsers ? "spin" : undefined} />
                <span className="sr-only">Refresh</span>
              </button>
            </div>
          ) : null}
        </header>

        {error ? (
          <p className="banner error" role="alert">
            {error}
          </p>
        ) : null}

        {!isAdmin ? (
          <section className="card">
            <div className="card-head">
              <h2>You're signed in</h2>
            </div>
            <div className="member-view">
              <Avatar name={me.display_name} email={me.email} size="lg" />
              <div>
                <strong>{me.display_name || me.email}</strong>
                <p className="hint">{me.email}</p>
                <p className="hint">
                  Member of <strong>{me.tenant_name}</strong>. Only admins can see the full
                  list of people. Last sign-in: {formatTimestamp(me.last_login_at)}.
                </p>
              </div>
            </div>
          </section>
        ) : view === "overview" ? (
          <>
            <section className="stats">
              <StatCard
                label="People"
                value={loadingUsers && !users ? "—" : stats.total}
                hint="Signed in at least once"
                icon={<IconUsers />}
                tone="accent"
              />
              <StatCard
                label="Admins"
                value={loadingUsers && !users ? "—" : stats.admins}
                hint="Can view this dashboard"
                icon={<IconShield />}
              />
              <StatCard
                label="Members"
                value={loadingUsers && !users ? "—" : stats.members}
                hint="Regular access"
                icon={<IconGrid />}
              />
              <StatCard
                label="Active this week"
                value={loadingUsers && !users ? "—" : stats.activeWeek}
                hint="Signed in within 7 days"
                icon={<IconActivity />}
                tone="warm"
              />
            </section>

            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Recent sign-ins</h2>
                  <p className="hint">Latest activity for @{me.workspace_domain}</p>
                </div>
                <button type="button" className="link" onClick={() => setView("people")}>
                  View all people →
                </button>
              </div>
              {loadingUsers && !users ? (
                <TableSkeleton rows={3} />
              ) : (
                <UserTable
                  users={recent}
                  currentUserId={me.id}
                  compact
                  emptyTitle="No sign-ins yet"
                  emptyBody="You'll see people here as soon as they sign in with Google."
                />
              )}
            </section>
          </>
        ) : (
          <section className="card">
            <div className="card-head">
              <div>
                <h2>Everyone in {me.tenant_name}</h2>
                <p className="hint">
                  {filtered.length} of {stats.total} shown · isolated to your tenant
                </p>
              </div>
              <div className="segmented" role="group" aria-label="Filter by role">
                {(
                  [
                    ["all", "All"],
                    ["admin", "Admins"],
                    ["user", "Members"],
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
            {loadingUsers && !users ? (
              <TableSkeleton rows={5} />
            ) : (
              <UserTable
                users={filtered}
                currentUserId={me.id}
                emptyTitle={query || roleFilter !== "all" ? "No matches" : "No people yet"}
                emptyBody={
                  query || roleFilter !== "all"
                    ? "Try a different search or clear the role filter."
                    : "Everyone who signs in with a matching Google account will appear here."
                }
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
    <div className="skeleton-table" aria-busy="true" aria-label="Loading">
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
