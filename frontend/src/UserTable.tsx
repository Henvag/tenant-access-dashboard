import { TenantUser } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, isWithinDays, relativeTime } from "./format";
import { TKey, useLang } from "./i18n";

type Props = {
  users: TenantUser[];
  currentUserId?: string;
  emptyTitle: string;
  emptyBody: string;
  compact?: boolean;
};

function activity(user: TenantUser): { key: TKey; tone: string } {
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
}: Props) {
  const { lang, t } = useLang();

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
      <table className={compact ? "table compact" : "table"}>
        <thead>
          <tr>
            <th>{t("table.person")}</th>
            <th>{t("table.role")}</th>
            {!compact ? <th>{t("table.activity")}</th> : null}
            <th className="num">{t("table.lastSignin")}</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const state = activity(user);
            const isYou = user.id === currentUserId;
            return (
              <tr key={user.id}>
                <td>
                  <div className="person">
                    <Avatar name={user.display_name} email={user.email} size="sm" />
                    <div className="person-text">
                      <span className="person-name">
                        {user.display_name || user.email.split("@")[0]}
                        {isYou ? <span className="you">{t("table.you")}</span> : null}
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
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
