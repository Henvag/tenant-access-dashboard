import { useState } from "react";
import { setUserDisabled, setUserRole, TenantUser, UserRole } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, isWithinDays, messageForApiError, relativeTime } from "./format";
import { TKey, useLang } from "./i18n";
import { IconShield, IconShieldOutline } from "./Icons";
import RowMenu, { MenuItem } from "./RowMenu";
import Tip from "./Tooltip";

type Props = {
  users: TenantUser[];
  currentUserId?: string;
  /** Signed-in user is the company owner (can promote/demote). */
  actorIsOwner?: boolean;
  emptyTitle: string;
  emptyBody: string;
  compact?: boolean;
  canManage?: boolean;
  onUserUpdated?: (user: TenantUser) => void;
};

function activity(user: TenantUser): { key: TKey; tone: string } {
  if (user.disabled) return { key: "status.disabled", tone: "bad" };
  if (!user.last_login_at) return { key: "activity.never", tone: "idle" };
  if (isWithinDays(user.last_login_at, 7)) return { key: "activity.active", tone: "ok" };
  if (isWithinDays(user.last_login_at, 30)) return { key: "activity.recent", tone: "warn" };
  return { key: "activity.inactive", tone: "idle" };
}

function RoleBadge({ user }: { user: TenantUser }) {
  const { t } = useLang();
  if (user.role === "admin" && user.is_owner) {
    return (
      <Tip label={t("role.ownerHint")}>
        <span className="pill pill-solid" tabIndex={0}>
          <IconShield width={12} height={12} />
          {t("role.admin")}
        </span>
      </Tip>
    );
  }
  if (user.role === "admin") {
    return (
      <Tip label={t("role.adminHint")}>
        <span className="pill pill-accent" tabIndex={0}>
          <IconShieldOutline width={12} height={12} />
          {t("role.admin")}
        </span>
      </Tip>
    );
  }
  return <span className="pill">{t("role.member")}</span>;
}

export default function UserTable({
  users,
  currentUserId,
  actorIsOwner = false,
  emptyTitle,
  emptyBody,
  compact = false,
  canManage = false,
  onUserUpdated,
}: Props) {
  const { lang, t } = useLang();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function runAction(userId: string, action: () => Promise<TenantUser>) {
    setBusyId(userId);
    setActionError(null);
    try {
      const updated = await action();
      onUserUpdated?.(updated);
    } catch (err) {
      const code = err instanceof Error ? err.message : "generic";
      setActionError(messageForApiError(code, lang));
    } finally {
      setBusyId(null);
    }
  }

  function toggleDisabled(user: TenantUser) {
    const nextDisabled = !user.disabled;
    if (nextDisabled && !window.confirm(t("people.disableConfirm", { email: user.email }))) {
      return;
    }
    void runAction(user.id, () => setUserDisabled(user.id, nextDisabled));
  }

  function changeRole(user: TenantUser, role: UserRole) {
    if (role === "user" && !window.confirm(t("people.demoteConfirm", { email: user.email }))) {
      return;
    }
    void runAction(user.id, () => setUserRole(user.id, role));
  }

  if (users.length === 0) {
    return (
      <div className="empty">
        <div className="empty-art" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <h3>{emptyTitle}</h3>
        <p>{emptyBody}</p>
      </div>
    );
  }

  const showActions = canManage && !compact;

  return (
    <div className="table-wrap">
      {actionError ? <p className="banner error">{actionError}</p> : null}
      <table className={compact ? "table compact" : "table"}>
        <thead>
          <tr>
            <th className="col-person">{t("table.person")}</th>
            <th>{t("table.role")}</th>
            {!compact ? <th className="col-optional">{t("table.activity")}</th> : null}
            <th className="num">{t("table.lastSignin")}</th>
            {showActions ? (
              <th className="col-actions">
                <span className="sr-only">{t("people.actions")}</span>
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const state = activity(user);
            const isYou = user.id === currentUserId;
            const busy = busyId === user.id;
            const canDisable = !isYou && !user.is_owner && (actorIsOwner || user.role === "user");
            const showPromote = actorIsOwner && !isYou && !user.is_owner && user.role === "user";
            const showDemote = actorIsOwner && !isYou && !user.is_owner && user.role === "admin";

            const items: MenuItem[] = [];
            if (showPromote) {
              items.push({
                key: "promote",
                label: t("people.promote"),
                onSelect: () => changeRole(user, "admin"),
              });
            }
            if (showDemote) {
              items.push({
                key: "demote",
                label: t("people.demote"),
                onSelect: () => changeRole(user, "user"),
              });
            }
            if (canDisable) {
              items.push({
                key: "access",
                label: user.disabled ? t("people.enable") : t("people.disable"),
                danger: !user.disabled,
                onSelect: () => toggleDisabled(user),
              });
            }

            return (
              <tr key={user.id} className={user.disabled ? "row-disabled" : undefined}>
                <td className="col-person">
                  <div className="person">
                    <Avatar name={user.display_name} email={user.email} size="sm" />
                    <div className="person-text">
                      <span className="person-name">
                        <span className="name-text">
                          {user.display_name || user.email.split("@")[0]}
                        </span>
                        {isYou ? (
                          <span className="pill pill-xs pill-accent">{t("table.you")}</span>
                        ) : null}
                        {user.disabled ? (
                          <span className="pill pill-xs pill-danger">{t("status.disabled")}</span>
                        ) : null}
                      </span>
                      <span className="person-email">{user.email}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <RoleBadge user={user} />
                </td>
                {!compact ? (
                  <td className="col-optional">
                    <span className={`dot-label tone-${state.tone}`}>
                      <i />
                      {t(state.key)}
                    </span>
                  </td>
                ) : null}
                <td className="num">
                  {user.last_login_at ? (
                    <Tip label={formatTimestamp(user.last_login_at, lang)}>
                      {relativeTime(user.last_login_at, lang)}
                    </Tip>
                  ) : (
                    relativeTime(user.last_login_at, lang)
                  )}
                </td>
                {showActions ? (
                  <td className="col-actions">
                    {items.length === 0 ? (
                      <span className="muted">{"\u2014"}</span>
                    ) : (
                      <RowMenu items={items} busy={busy} label={t("people.moreActions")} />
                    )}
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
