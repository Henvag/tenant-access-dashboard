import { TenantUser } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, isWithinDays, relativeTime } from "./format";

type Props = {
  users: TenantUser[];
  currentUserId?: string;
  emptyTitle?: string;
  emptyBody?: string;
  compact?: boolean;
};

function activity(user: TenantUser): { label: string; tone: string } {
  if (!user.last_login_at) return { label: "Never signed in", tone: "idle" };
  if (isWithinDays(user.last_login_at, 7)) return { label: "Active", tone: "ok" };
  if (isWithinDays(user.last_login_at, 30)) return { label: "Recent", tone: "warn" };
  return { label: "Inactive", tone: "idle" };
}

export default function UserTable({
  users,
  currentUserId,
  emptyTitle = "No people yet",
  emptyBody = "Everyone who signs in with a matching Google account will appear here.",
  compact = false,
}: Props) {
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
            <th>Person</th>
            <th>Role</th>
            {!compact ? <th>Activity</th> : null}
            <th className="num">Last sign-in</th>
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
                        {isYou ? <span className="you">You</span> : null}
                      </span>
                      <span className="person-email">{user.email}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <span className={`role role-${user.role}`}>
                    {user.role === "admin" ? "Admin" : "Member"}
                  </span>
                </td>
                {!compact ? (
                  <td>
                    <span className={`dot-label tone-${state.tone}`}>
                      <i />
                      {state.label}
                    </span>
                  </td>
                ) : null}
                <td className="num" title={formatTimestamp(user.last_login_at)}>
                  {relativeTime(user.last_login_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
