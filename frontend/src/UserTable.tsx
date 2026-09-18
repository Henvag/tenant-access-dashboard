import { TenantUser } from "./api";
import { formatTimestamp } from "./format";

type Props = {
  users: TenantUser[];
};

export default function UserTable({ users }: Props) {
  if (users.length === 0) {
    return <p className="muted">No one from this tenant has signed in yet.</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Last sign-in</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.display_name || "—"}</td>
              <td>{user.email}</td>
              <td>
                <span className={`role role-${user.role}`}>{user.role}</span>
              </td>
              <td>{formatTimestamp(user.last_login_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
