import { useState } from "react";
import { setUserDisabled, TenantUser } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, isWithinDays, messageForApiError, relativeTime } from "./format";
import { TKey, useLang } from "./i18n";

type Props = {
  users: TenantUser[];
  currentUserId?: string;
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

export default function UserTable({
  users,
  currentUserId,
  emptyTitle,
  emptyBody,
  compact = false,
  canManage = false,
  onUserUpdated,
}: Props) {
  const { lang, t } = useLang();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function toggleDisabled(user: TenantUser) {
    const nextDisabled = !user.disabled;
    if (nextDisabled && !window.confirm(t("people.disableConfirm", { email: user.email }))) {
      return;
    }
    setBusyId(user.id);
    setActionError(null);
    try {
      const updated = await setUserDisabled(user.id, nextDisabled);
      onUserUpdated?.(updated);
    } catch (err) {
      const code = err instanceof Error ? err.message : "generic";
      setActionError(messageForApiError(code, lang));
    } finally {
      setBusyId(null);
    }
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

  return (
    <div className="table-wrap">
      {actionError ? <p className="banner error">{actionError}</p> : null}
      <table className={compact ? "table compact" : "table"}>
        <thead>
          <tr>
            <th>{t("table.person")}</th>
            <th>{t("table.role")}</th>
            {!compact ? <th>{t("table.activity")}</th> : null}
            <th className="num">{t("table.lastSignin")}</th>
            {canManage && !compact ? <th className="num">{t("table.access")}</th> : null}
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const state = activity(user);
            const isYou = user.id === currentUserId;
            const busy = busyId === user.id;
            return (
              <tr key={user.id} className={user.disabled ? "row-disabled" : undefined}>
                <td>
                  <div className="person">
                    <Avatar name={user.display_name} email={user.email} size="sm" />
                    <div className="person-text">
                      <span className="person-name">
                        {user.display_name || user.email.split("@")[0]}
                        {isYou ? <span className="you">{t("table.you")}</span> : null}
                        {user.disabled ? (
                          <span className="status-pill">{t("status.disabled")}</span>
                        ) : null}
                      </span>
                      <span className="person-email">{user.email}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <span className={`role role-${user.role}`}>
                    {user.role === "admin" ? t("role.admin") : t("role.member")}
                  </span>
                </td>
                {!compact ? (
                  <td>
                    <span className={`dot-label tone-${state.tone}`}>
                      <i />
                      {t(state.key)}
                    </span>
                  </td>
                ) : null}
                <td className="num" title={formatTimestamp(user.last_login_at, lang)}>
                  {relativeTime(user.last_login_at, lang)}
                </td>
                {canManage && !compact ? (
                  <td className="num">
                    {isYou ? (
                      <span className="muted">—</span>
                    ) : (
                      <button
                        type="button"
                        className={user.disabled ? "btn btn-ghost btn-table" : "btn btn-ghost btn-table danger"}
                        disabled={busy}
                        onClick={() => void toggleDisabled(user)}
                      >
                        {busy
                          ? t("people.working")
                          : user.disabled
                            ? t("people.enable")
                            : t("people.disable")}
                      </button>
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
