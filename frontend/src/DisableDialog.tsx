import { useEffect, useState } from "react";
import { listPersonApps, PersonApp, TenantUser } from "./api";
import AppMark from "./AppMark";
import { relativeTime } from "./format";
import { useLang } from "./i18n";
import Modal from "./Modal";

type Props = {
  user: TenantUser;
  onCancel: () => void;
  onConfirm: () => void;
};

/** Shows what disabling a person cuts off before the admin confirms. */
export default function DisableDialog({ user, onCancel, onConfirm }: Props) {
  const { lang, t } = useLang();
  const [apps, setApps] = useState<PersonApp[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listPersonApps(user.id)
      .then((rows) => {
        if (!cancelled) setApps(rows);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [user.id]);

  const name = user.display_name || user.email;
  const detail = (app: PersonApp) =>
    [
      app.has_access ? null : t("offboard.noAccessNow"),
      app.last_used_at
        ? t("offboard.lastUsed", { when: relativeTime(app.last_used_at, lang) })
        : null,
    ]
      .filter(Boolean)
      .join(" · ");

  return (
    <Modal title={t("offboard.title", { name })} hint={t("offboard.hint")} onClose={onCancel}>
      {failed ? (
        <p className="hint">{t("offboard.loadFailed")}</p>
      ) : apps === null ? (
        <p className="hint">{t("offboard.loading")}</p>
      ) : apps.length === 0 ? (
        <p className="hint">{t("offboard.none")}</p>
      ) : (
        <>
          <h3 className="offboard-heading">{t("offboard.appsHeading")}</h3>
          <ul className="app-list offboard-list">
            {apps.map((app) => (
              <li key={app.client_id} className="app-row">
                <div className="app-row-main">
                  <AppMark name={app.name} size="sm" />
                  <div>
                    <strong>{app.name}</strong>
                    {detail(app) ? <p className="hint">{detail(app)}</p> : null}
                  </div>
                </div>
                <span className={app.can_log_out ? "pill pill-xs pill-ok" : "pill pill-xs pill-warn"}>
                  {app.can_log_out ? t("offboard.logsOutNow") : t("offboard.endsOnItsOwn")}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          {t("offboard.cancel")}
        </button>
        <button type="button" className="btn btn-danger" onClick={onConfirm}>
          {t("offboard.confirm")}
        </button>
      </div>
    </Modal>
  );
}
