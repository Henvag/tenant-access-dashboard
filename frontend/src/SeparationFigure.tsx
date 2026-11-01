import { useEffect, useRef, useState } from "react";
import { useLang } from "./i18n";

type Row = { email: string; company: "a" | "b" };

/** One shared users table, two companies' rows mixed together, as they are in the real database. */
const ROWS: Row[] = [
  { email: "ingrid@a.no", company: "a" },
  { email: "kari@b.no", company: "b" },
  { email: "jonas@a.no", company: "a" },
  { email: "ola@b.no", company: "b" },
  { email: "nina@b.no", company: "b" },
  { email: "sofie@a.no", company: "a" },
];

const TABLE_TOP = 150;
const HEAD_H = 28;
const ROW_H = 34;

/**
 * A ten-second loop for the Security section. Company A's request returns only A's rows,
 * then B's request returns only B's, then A reaching for B's row is refused at the
 * row-level security line. It runs only while on screen, and holds still with reduced motion.
 */
export default function SeparationFigure() {
  const { t } = useLang();
  const ref = useRef<HTMLElement | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setRunning(entry.isIntersecting),
      {
        threshold: 0.25,
      },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const companyA = t("security.figure.companyA");
  const companyB = t("security.figure.companyB");

  return (
    <figure ref={ref} className={running ? "sep-figure running" : "sep-figure"}>
      <svg
        className="sep-svg"
        viewBox="0 0 360 382"
        role="img"
        aria-labelledby="sep-caption"
      >
        {/* Requests */}
        <Request x={0} label={companyA} company="a" />
        <Request x={190} label={companyB} company="b" />

        {/* Row-level security line */}
        <line className="sep-gate" x1="0" y1="110" x2="360" y2="110" />
        <text className="sep-gate-label" x="360" y="102" textAnchor="end">
          {t("security.figure.gate")}
        </text>

        {/* What each request travels */}
        <path
          className="sep-anim sep-path sep-path-a"
          d="M85 56 V150"
          pathLength={1}
        />
        <path
          className="sep-anim sep-path sep-path-b"
          d="M275 56 V150"
          pathLength={1}
        />
        <path
          className="sep-anim sep-path sep-path-x"
          d="M85 56 C85 92 170 104 222 110"
          pathLength={1}
        />
        <g className="sep-anim sep-refused">
          <path className="sep-cross" d="M216 104 L228 116 M228 104 L216 116" />
          <text
            className="sep-refused-label"
            x="222"
            y="136"
            textAnchor="middle"
          >
            {t("security.figure.refused")}
          </text>
        </g>

        {/* The shared table */}
        <rect
          className="sep-table"
          x="0.5"
          y={TABLE_TOP + 0.5}
          width="359"
          height={HEAD_H + ROW_H * ROWS.length - 1}
          rx="6"
        />
        <text className="sep-table-name" x="14" y={TABLE_TOP + 19}>
          users
        </text>
        {ROWS.map((row, i) => {
          const y = TABLE_TOP + HEAD_H + i * ROW_H;
          return <line key={row.email} className="sep-row-rule" x1="1" y1={y} x2="359" y2={y} />;
        })}
        {ROWS.map((row, i) => {
          const y = TABLE_TOP + HEAD_H + i * ROW_H;
          return (
            <g
              key={row.email}
              className={`sep-anim sep-row sep-row-${row.company}`}
            >
              <circle
                className={`sep-dot-${row.company}`}
                cx="18"
                cy={y + ROW_H / 2}
                r="4"
              />
              <text className="sep-row-email" x="32" y={y + ROW_H / 2 + 4}>
                {row.email}
              </text>
              <text
                className="sep-row-company"
                x="346"
                y={y + ROW_H / 2 + 4}
                textAnchor="end"
              >
                {row.company === "a" ? companyA : companyB}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption id="sep-caption">{t("security.figure.caption")}</figcaption>
    </figure>
  );
}

function Request({
  x,
  label,
  company,
}: {
  x: number;
  label: string;
  company: "a" | "b";
}) {
  return (
    <g>
      <rect
        className="sep-req"
        x={x + 0.5}
        y="0.5"
        width="169"
        height="55"
        rx="6"
      />
      <rect
        className={`sep-anim sep-req-on sep-req-on-${company}`}
        x={x + 0.5}
        y="0.5"
        width="169"
        height="55"
        rx="6"
      />
      <circle className={`sep-dot-${company}`} cx={x + 18} cy="22" r="4" />
      <text className="sep-req-name" x={x + 30} y="27">
        {label}
      </text>
      <text className="sep-req-call" x={x + 14} y="44">
        GET /users
      </text>
    </g>
  );
}
