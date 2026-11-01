import { KeyboardEvent, ReactNode, useEffect, useState } from "react";
import { TKey, useLang } from "./i18n";
import { IconChevronLeft, IconChevronRight, IconRefresh } from "./Icons";
import appsShot from "./assets/tour/apps.webp";
import auditShot from "./assets/tour/audit.webp";
import grafanaShot from "./assets/tour/grafana.webp";
import overviewShot from "./assets/tour/overview.webp";
import peopleShot from "./assets/tour/people.webp";

type Step = {
  id: "overview" | "people" | "apps" | "sso" | "audit";
  image: string;
  /** Address shown in the fake browser bar. */
  url: string;
  /** Where the pulsing marker sits, in percent of the screenshot. */
  hotspot: { x: number; y: number };
};

// Screenshots of the demo company (scripts/capture-demo.mjs), 1440×900.
const STEPS: Step[] = [
  { id: "overview", image: overviewShot, url: "tenantaccess.me", hotspot: { x: 41, y: 42.5 } },
  { id: "people", image: peopleShot, url: "tenantaccess.me/?view=people", hotspot: { x: 66, y: 68 } },
  { id: "apps", image: appsShot, url: "tenantaccess.me/?view=apps", hotspot: { x: 33.5, y: 38.5 } },
  {
    id: "sso",
    image: grafanaShot,
    url: "tenant-access-grafana.onrender.com/login",
    hotspot: { x: 50, y: 60 },
  },
  { id: "audit", image: auditShot, url: "tenantaccess.me/?view=audit", hotspot: { x: 62, y: 79.5 } },
];

const TOTAL = STEPS.length;

type Props = {
  /** Call to action on the last card, e.g. the live demo button. */
  action: ReactNode;
};

export default function ProductTour({ action }: Props) {
  const { t } = useLang();
  // TOTAL is the closing card that hands over to the live demo.
  const [index, setIndex] = useState(0);
  const done = index >= TOTAL;
  const step = STEPS[Math.min(index, TOTAL - 1)];

  useEffect(() => {
    // Warm the cache so each click swaps instantly.
    for (const s of STEPS) {
      const img = new Image();
      img.src = s.image;
    }
  }, []);

  function go(next: number) {
    setIndex(Math.max(0, Math.min(TOTAL, next)));
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowRight") go(index + 1);
    if (event.key === "ArrowLeft") go(index - 1);
  }

  const titleKey = (done ? "tour.done.title" : `tour.${step.id}.title`) as TKey;
  const bodyKey = (done ? "tour.done.body" : `tour.${step.id}.body`) as TKey;

  return (
    <div className="tour" onKeyDown={onKeyDown}>
      <div className="tour-frame">
        <div className="tour-chrome" aria-hidden="true">
          <span className="tour-dots">
            <i />
            <i />
            <i />
          </span>
          <span className="tour-url">{step.url}</span>
        </div>
        <div className="tour-screen">
          {STEPS.map((s, i) => (
            <img
              key={s.id}
              src={s.image}
              alt={i === Math.min(index, TOTAL - 1) ? t(`tour.${s.id}.title` as TKey) : ""}
              className={i === Math.min(index, TOTAL - 1) ? "tour-shot active" : "tour-shot"}
              width={1440}
              height={900}
              loading={i === 0 ? "eager" : "lazy"}
              decoding="async"
            />
          ))}
          {done ? (
            <div className="tour-finale">
              <h3>{t("tour.done.title")}</h3>
              <div className="tour-finale-actions">{action}</div>
              <button type="button" className="link" onClick={() => go(0)}>
                <IconRefresh width={14} height={14} />
                {t("tour.restart")}
              </button>
            </div>
          ) : (
            <button
              key={step.id}
              type="button"
              className="tour-hotspot"
              style={{ left: `${step.hotspot.x}%`, top: `${step.hotspot.y}%` }}
              onClick={() => go(index + 1)}
              aria-label={t("tour.next")}
            />
          )}
        </div>
      </div>

      <div className="tour-caption" aria-live="polite">
        <p className="sr-only">
          {done ? "" : t("tour.step", { n: String(index + 1), total: String(TOTAL) })}
        </p>
        <h3>{t(titleKey)}</h3>
        <p className="tour-body">{t(bodyKey)}</p>
        <div className="tour-nav">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => go(index - 1)}
            disabled={index === 0}
          >
            <IconChevronLeft width={16} height={16} />
            {t("tour.back")}
          </button>
          <div className="tour-steps" role="group" aria-label={t("tour.eyebrow")}>
            {[...STEPS.map((s) => s.id), "done"].map((id, i) => (
              <button
                key={id}
                type="button"
                className={i === index ? "tour-step-dot active" : "tour-step-dot"}
                aria-label={t("tour.hotspot", { n: String(i + 1) })}
                aria-current={i === index ? "step" : undefined}
                onClick={() => go(i)}
              />
            ))}
          </div>
          {done ? (
            <span className="tour-nav-spacer" />
          ) : (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => go(index + 1)}>
              {t("tour.next")}
              <IconChevronRight width={16} height={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
