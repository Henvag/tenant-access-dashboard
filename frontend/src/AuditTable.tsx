import { AuditEvent } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, relativeTime } from "./format";
import { useLang } from "./i18n";
import { IconGoogle, IconMicrosoft } from "./Icons";

type Props = {
  events: AuditEvent[];
  emptyTitle: string;
  emptyBody: string;
  compact?: boolean;
};

export default function AuditTable({ events, emptyTitle, emptyBody, compact = false }: Props) {
  const { lang, t } = useLang();

  if (events.length === 0) {
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
            <th>{t("audit.event")}</th>
            <th>{t("audit.idp")}</th>
            {!compact ? <th>{t("audit.ip")}</th> : null}
            <th className="num">{t("audit.when")}</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>
                <div className="person">
                  <Avatar name={event.display_name} email={event.email} size="sm" />
                  <div className="person-text">
                    <span className="person-name">
                      {event.display_name || event.email.split("@")[0]}
                    </span>
                    <span className="person-email">{event.email}</span>
                  </div>
                </div>
              </td>
              <td>
                <span className="role role-user">{t("audit.login")}</span>
              </td>
              <td>
                <span className="idp-label">
                  {event.idp === "microsoft" ? <IconMicrosoft width={14} height={14} /> : <IconGoogle width={14} height={14} />}
                  {event.idp === "microsoft" ? t("idp.microsoft") : t("idp.google")}
                </span>
              </td>
              {!compact ? (
                <td>
                  <span className="mono muted">{event.ip_address || "—"}</span>
                </td>
              ) : null}
              <td className="num" title={formatTimestamp(event.created_at, lang)}>
                {relativeTime(event.created_at, lang)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
