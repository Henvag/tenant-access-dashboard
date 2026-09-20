import { useEffect, useState } from "react";
import { listMyApps, MyApp } from "./api";
import AppMark from "./AppMark";
import { useLang } from "./i18n";
import { IconExternal, IconPlug } from "./Icons";
import Tip from "./Tooltip";

/** Launcher: apps this person is allowed to open. */
export default function AppTiles({ refreshKey = 0 }: { refreshKey?: number }) {
  const { t } = useLang();
  const [apps, setApps] = useState<MyApp[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    listMyApps()
      .then((list) => {
        if (!cancelled) setApps(list);
      })
      .catch(() => {
        if (!cancelled) setApps([]);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>{t("myapps.title")}</h2>
          <p className="hint">{t("myapps.hint")}</p>
        </div>
      </div>
      {apps === null ? (
        <div className="tile-grid" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <span className="tile sk" key={i} />
          ))}
        </div>
      ) : apps.length === 0 ? (
        <div className="empty-apps">
          <span className="empty-apps-icon" aria-hidden="true">
            <IconPlug width={22} height={22} />
          </span>
          <strong>{t("myapps.emptyTitle")}</strong>
          <p className="hint">{t("myapps.emptyBody")}</p>
          <p className="hint fine">{t("myapps.sessionHint")}</p>
        </div>
      ) : (
        <>
          <p className="hint fine myapps-session">{t("myapps.sessionHint")}</p>
          <div className="tile-grid">
            {apps.map((app) =>
              app.launch_url ? (
                <a
                  key={app.id}
                  className="tile"
                  href={app.launch_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <AppMark name={app.name} size="sm" />
                  <span className="tile-name">{app.name}</span>
                  <IconExternal width={14} height={14} className="tile-ext" />
                </a>
              ) : (
                <Tip key={app.id} label={t("myapps.noLaunch")}>
                  <span className="tile tile-static" tabIndex={0}>
                    <AppMark name={app.name} size="sm" />
                    <span className="tile-name">{app.name}</span>
                  </span>
                </Tip>
              ),
            )}
          </div>
        </>
      )}
    </section>
  );
}
