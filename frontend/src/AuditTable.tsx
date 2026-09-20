import { Fragment, useState } from "react";
import { AuditEvent } from "./api";
import Avatar from "./Avatar";
import { formatTimestamp, relativeTime } from "./format";
import { TKey, useLang } from "./i18n";
import { IconChevron, IconGoogle, IconMicrosoft } from "./Icons";
import Tip from "./Tooltip";

type Props = {
  events: AuditEvent[];
  emptyTitle: string;
  emptyBody: string;
  compact?: boolean;
};

/** Long, human sentence for the expanded panel. */
const ERROR_KEYS: Record<string, TKey> = {
  no_tenant: "auth.no_tenant",
  invalid_domain: "auth.invalid_domain",
  domain_mismatch: "auth.domain_mismatch",
  missing_claims: "auth.missing_claims",
  unverified_email: "auth.unverified_email",
  identity_conflict: "auth.identity_conflict",
  user_disabled: "auth.user_disabled",
  oidc_failed: "auth.oidc_failed",
};

/** Two-word chip for the table row. */
const REASON_KEYS: Record<string, TKey> = {
  no_tenant: "reason.no_tenant",
  invalid_domain: "reason.invalid_domain",
  domain_mismatch: "reason.domain_mismatch",
  missing_claims: "reason.missing_claims",
  unverified_email: "reason.unverified_email",
  identity_conflict: "reason.identity_conflict",
  user_disabled: "reason.user_disabled",
  oidc_failed: "reason.oidc_failed",
};

type Tone = "neutral" | "accent" | "ok" | "warn" | "danger";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "pill",
  accent: "pill pill-accent",
  ok: "pill pill-ok",
  warn: "pill pill-warn",
  danger: "pill pill-danger",
};

type Presentation = {
  labelKey: TKey;
  tone: Tone;
  /** Short chip shown in the Reason column; null renders a muted dash. */
  reason: { text: string; tone: Tone } | null;
  /** Full sentence shown in the expanded panel. */
  sentence: string;
  warn: boolean;
};

const DENIAL_REASON_KEYS: Record<string, TKey> = {
  not_assigned: "reason.not_assigned",
  admins_only: "reason.admins_only",
  wrong_tenant: "reason.wrong_tenant",
  app_disabled: "reason.app_disabled",
  user_disabled: "reason.user_disabled",
};

function present(event: AuditEvent, t: (key: TKey, vars?: Record<string, string>) => string): Presentation {
  const code = event.error_code ?? undefined;
  const app = event.details?.app ?? "-";
  const by = event.details?.by ?? "";

  switch (event.event_type) {
    case "app_login":
      return {
        labelKey: "audit.appLogin",
        tone: "accent",
        reason: { text: app, tone: "neutral" },
        sentence: t("audit.appLoginDetail", { app }),
        warn: false,
      };
    case "app_login_denied": {
      const reasonKey = code ? DENIAL_REASON_KEYS[code] : undefined;
      return {
        labelKey: "audit.appLoginDenied",
        tone: "danger",
        reason: { text: reasonKey ? t(reasonKey) : app, tone: "danger" },
        sentence: `${t("audit.appLoginDeniedDetail", { app })}${
          reasonKey ? ` - ${t(reasonKey)}` : ""
        }`,
        warn: true,
      };
    }
    case "app_created":
      return {
        labelKey: "audit.appCreated",
        tone: "ok",
        reason: { text: app, tone: "neutral" },
        sentence: t("audit.appCreatedDetail", { app }),
        warn: false,
      };
    case "app_deleted":
      return {
        labelKey: "audit.appDeleted",
        tone: "warn",
        reason: { text: app, tone: "neutral" },
        sentence: t("audit.appDeletedDetail", { app }),
        warn: false,
      };
    case "app_access_granted":
      return {
        labelKey: "audit.appGranted",
        tone: "ok",
        reason: { text: app, tone: "neutral" },
        sentence: t("audit.appGrantedDetail", { app, by }),
        warn: false,
      };
    case "app_access_revoked":
      return {
        labelKey: "audit.appRevoked",
        tone: "warn",
        reason: { text: app, tone: "neutral" },
        sentence: t("audit.appRevokedDetail", { app, by }),
        warn: false,
      };
    case "login_failed": {
      const reasonKey = code ? REASON_KEYS[code] : undefined;
      const sentenceKey = code ? ERROR_KEYS[code] : undefined;
      return {
        labelKey: "audit.loginFailed",
        tone: "danger",
        reason: {
          text: reasonKey ? t(reasonKey) : code ? code : t("reason.unknown"),
          tone: "danger",
        },
        sentence: sentenceKey
          ? t(sentenceKey)
          : code
            ? t("auth.generic", { code })
            : t("audit.failedUnknown"),
        warn: true,
      };
    }
    case "user_disabled":
      return {
        labelKey: "audit.userDisabled",
        tone: "warn",
        reason: { text: t("reason.byAdmin"), tone: "neutral" },
        sentence: t("audit.userDisabledDetail"),
        warn: true,
      };
    case "user_enabled":
      return {
        labelKey: "audit.userEnabled",
        tone: "ok",
        reason: { text: t("reason.byAdmin"), tone: "neutral" },
        sentence: t("audit.userEnabledDetail"),
        warn: false,
      };
    case "role_changed": {
      const toAdmin = event.details?.to_role
        ? event.details.to_role === "admin"
        : code
          ? code.endsWith("->admin")
          : false;
      return {
        labelKey: "audit.roleChanged",
        tone: "accent",
        reason: { text: toAdmin ? t("reason.toAdmin") : t("reason.toMember"), tone: "accent" },
        sentence: t("audit.roleChangedDetail"),
        warn: false,
      };
    }
    default:
      return {
        labelKey: "audit.login",
        tone: "neutral",
        reason: null,
        sentence: t("audit.loginDetail"),
        warn: false,
      };
  }
}

function IdpLabel({ idp, t }: { idp: AuditEvent["idp"]; t: (key: TKey) => string }) {
  return (
    <span className="idp-label">
      {idp === "microsoft" ? (
        <IconMicrosoft width={14} height={14} />
      ) : (
        <IconGoogle width={14} height={14} />
      )}
      {idp === "microsoft" ? t("idp.microsoft") : t("idp.google")}
    </span>
  );
}

export default function AuditTable({ events, emptyTitle, emptyBody, compact = false }: Props) {
  const { lang, t } = useLang();
  const [openId, setOpenId] = useState<string | null>(null);

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

  const toggle = (id: string) => setOpenId((current) => (current === id ? null : id));
  // Person, Event, Reason, [IdP], When, chevron
  const columnCount = compact ? 5 : 6;

  return (
    <div className="table-wrap">
      <table className={compact ? "table compact" : "table"}>
        <thead>
          <tr>
            <th className="col-person">{t("table.person")}</th>
            <th>{t("audit.event")}</th>
            <th>{t("audit.reason")}</th>
            {!compact ? <th className="col-optional">{t("audit.idp")}</th> : null}
            <th className="num">{t("audit.when")}</th>
            <th className="col-chevron">
              <span className="sr-only">{t("audit.details")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const view = present(event, t);
            const open = openId === event.id;
            const exact = formatTimestamp(event.created_at, lang);
            const panelId = `audit-${event.id}`;

            return (
              <Fragment key={event.id}>
                <tr
                  className={open ? "row-click row-open" : "row-click"}
                  onClick={() => toggle(event.id)}
                >
                  <td className="col-person">
                    <div className="person">
                      <Avatar name={event.display_name} email={event.email} size="sm" />
                      <div className="person-text">
                        <span className="person-name">
                          <span className="name-text">
                            {event.display_name || event.email.split("@")[0]}
                          </span>
                        </span>
                        <span className="person-email">{event.email}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={TONE_CLASS[view.tone]}>{t(view.labelKey)}</span>
                  </td>
                  <td>
                    {view.reason ? (
                      <span className={TONE_CLASS[view.reason.tone]}>{view.reason.text}</span>
                    ) : (
                      <span className="muted">{"-"}</span>
                    )}
                  </td>
                  {!compact ? (
                    <td className="col-optional">
                      <IdpLabel idp={event.idp} t={t} />
                    </td>
                  ) : null}
                  <td className="num">
                    <Tip label={exact}>{relativeTime(event.created_at, lang)}</Tip>
                  </td>
                  <td className="col-chevron">
                    <button
                      type="button"
                      className="btn-icon"
                      aria-expanded={open}
                      aria-controls={panelId}
                      aria-label={open ? t("audit.collapse") : t("audit.expand")}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggle(event.id);
                      }}
                    >
                      <IconChevron
                        width={15}
                        height={15}
                        className={open ? "chev open" : "chev"}
                      />
                    </button>
                  </td>
                </tr>
                {open ? (
                  <tr className="row-detail" id={panelId}>
                    <td colSpan={columnCount}>
                      <dl className="detail-grid">
                        <div className="wide">
                          <dt>{t("audit.details")}</dt>
                          <dd className={view.warn ? "warn" : undefined}>{view.sentence}</dd>
                        </div>
                        <div>
                          <dt>{t("audit.code")}</dt>
                          <dd>{event.error_code ? <code>{event.error_code}</code> : "-"}</dd>
                        </div>
                        <div>
                          <dt>{t("audit.idp")}</dt>
                          <dd>
                            <IdpLabel idp={event.idp} t={t} />
                          </dd>
                        </div>
                        <div>
                          <dt>{t("audit.ip")}</dt>
                          <dd className="mono">{event.ip_address || "-"}</dd>
                        </div>
                        <div>
                          <dt>{t("audit.time")}</dt>
                          <dd>{exact}</dd>
                        </div>
                      </dl>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
