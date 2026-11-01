import { useEffect, useRef, useState } from "react";
import { useLang } from "./i18n";
import { IconRefresh } from "./Icons";

type Company = "a" | "b";
type Row = { company: Company; width: number };

/** One shared table, both companies' rows mixed together, as they are in the real database. */
const ROWS: Row[] = [
  { company: "a", width: 220 },
  { company: "b", width: 250 },
  { company: "a", width: 190 },
  { company: "b", width: 236 },
  { company: "b", width: 204 },
  { company: "a", width: 244 },
];

// Geometry, in viewBox units. The stage is 640 × 340 with 40 spare on each side for the hands.
const SLAB = { x: 120, y: 70, w: 400, h: 180 };
const PULL = 80; // how far each half travels
const ROW_X = 164; // dot of a row while the table is whole
const ROW_Y0 = 114;
const ROW_STEP = 22;
const FINAL_Y0 = 130;
const FINAL_STEP = 36;
const FINAL_W = 112;
// Left edge of each company's content once the halves have parted.
const FINAL_A = SLAB.x - PULL + 40;
const FINAL_B = SLAB.x + SLAB.w / 2 + PULL + 24;

/** The crack, top to bottom, near the middle of the slab. */
const CRACK: [number, number][] = [
  [322, 70],
  [312, 98],
  [328, 128],
  [314, 160],
  [330, 192],
  [316, 222],
  [324, 250],
];
const crackPath = `M${CRACK.map(([x, y]) => `${x} ${y}`).join(" L")}`;
const leftClip = `M80 40 L${CRACK.map(([x, y]) => `${x} ${y}`).join(" L")} L80 280 Z`;
const rightClip = `M560 40 L${CRACK.map(([x, y]) => `${x} ${y}`).join(" L")} L560 280 Z`;

/** Splinters that fly off the crack: x, y, size. */
const SHARDS: [number, number, number][] = [
  [318, 84, 9],
  [324, 110, 7],
  [316, 136, 11],
  [326, 168, 8],
  [314, 196, 10],
  [328, 214, 7],
  [320, 240, 9],
];
const SHARD_FLIGHT = [
  [-42, -38, -120],
  [36, -30, 140],
  [-56, -6, -200],
  [48, 12, 160],
  [-38, 30, -90],
  [44, 40, 220],
  [-26, 58, -160],
];

/** Where each row ends up: A's rows stack in the left half, B's in the right. */
function targets() {
  const seen: Record<Company, number> = { a: 0, b: 0 };
  return ROWS.map((row, i) => {
    const slot = seen[row.company]++;
    const finalX = row.company === "a" ? FINAL_A : FINAL_B;
    return {
      dx: finalX - ROW_X,
      dy: FINAL_Y0 + slot * FINAL_STEP - (ROW_Y0 + i * ROW_STEP),
    };
  });
}

/**
 * The Security section's picture: two hands grip one shared table, it cracks, and they
 * pull it apart so each company is left holding only its own rows, with row-level
 * security standing in the gap. GSAP plays it once when it scrolls into view; reduced
 * motion shows the end state.
 */
export default function SeparationFigure() {
  const { t } = useLang();
  const root = useRef<HTMLElement | null>(null);
  const timeline = useRef<{ restart: () => void; kill: () => void } | null>(null);
  const [reduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    let cancelled = false;
    let observer: IntersectionObserver | null = null;

    import("gsap").then(({ gsap }) => {
      if (cancelled) return;
      const q = gsap.utils.selector(el);
      const moves = targets();
      const tl = gsap.timeline({ paused: true, defaults: { ease: "power3.out" } });

      // Hands reach in and take hold.
      tl.from(q(".sep-hand-l"), { x: -260, duration: 0.8 }, 0)
        .from(q(".sep-hand-r"), { x: 260, duration: 0.8 }, 0)
        .from(q(".sep-finger"), { scaleX: 0.4, transformOrigin: "0% 50%", duration: 0.25, stagger: 0.03 }, 0.6)
        // Strain: the table shudders before it gives.
        .to(q(".sep-strain"), { opacity: 1, duration: 0.2 }, 0.95)
        .to(
          q(".sep-half, .sep-row, .sep-hand"),
          { x: "+=2", duration: 0.05, yoyo: true, repeat: 7, ease: "none" },
          0.95,
        )
        // It cracks.
        .fromTo(
          q(".sep-crack"),
          { strokeDashoffset: 1, opacity: 1 },
          { strokeDashoffset: 0, duration: 0.4, ease: "power2.in", immediateRender: false },
          1.3,
        )
        .to(q(".sep-table-name"), { opacity: 0, duration: 0.25 }, 1.5)
        // And comes apart.
        .to(q(".sep-half-l, .sep-hand-l"), { x: -PULL, duration: 1, ease: "power4.out" }, 1.75)
        .to(q(".sep-half-r, .sep-hand-r"), { x: PULL, duration: 1, ease: "power4.out" }, 1.75)
        .to(q(".sep-half-l"), { rotation: -3, svgOrigin: "120 160", duration: 0.3, yoyo: true, repeat: 1 }, 1.75)
        .to(q(".sep-half-r"), { rotation: 3, svgOrigin: "520 160", duration: 0.3, yoyo: true, repeat: 1 }, 1.75)
        .to(q(".sep-crack"), { opacity: 0, duration: 0.15 }, 1.75)
        .fromTo(
          q(".sep-shard"),
          { opacity: 1 },
          {
            immediateRender: false,
            x: (i: number) => SHARD_FLIGHT[i][0],
            y: (i: number) => SHARD_FLIGHT[i][1],
            rotation: (i: number) => SHARD_FLIGHT[i][2],
            opacity: 0,
            duration: 0.9,
            ease: "power2.out",
          },
          1.75,
        )
        .to(q(".sep-strain"), { opacity: 0, duration: 0.2 }, 2.2);

      // Each row goes to its own company's half.
      q(".sep-row").forEach((row: Element, i: number) => {
        tl.to(row, { x: moves[i].dx, y: moves[i].dy, duration: 0.85, ease: "power3.inOut" }, 1.75 + i * 0.05);
      });
      tl.to(q(".sep-row-bar"), { attr: { width: FINAL_W }, duration: 0.45, ease: "power2.out" }, 1.75)
        // Name the halves and put row-level security in the gap.
        .to(q(".sep-title"), { opacity: 1, duration: 0.4 }, 2.6)
        .fromTo(
          q(".sep-barrier"),
          { scaleY: 0, opacity: 0, svgOrigin: "320 160" },
          { scaleY: 1, opacity: 1, duration: 0.6, ease: "power3.out" },
          2.7,
        )
        .to(q(".sep-barrier-label"), { opacity: 1, duration: 0.4 }, 2.95)
        // The hands let go.
        .to(q(".sep-hand-l"), { x: -340, opacity: 0, duration: 0.7, ease: "power2.in" }, 3.3)
        .to(q(".sep-hand-r"), { x: 340, opacity: 0, duration: 0.7, ease: "power2.in" }, 3.3);

      timeline.current = tl;

      if (reduced) {
        tl.progress(1);
        return;
      }
      observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            tl.play();
            observer?.disconnect();
          }
        },
        { threshold: 0.5 },
      );
      observer.observe(el);
    });

    return () => {
      cancelled = true;
      observer?.disconnect();
      timeline.current?.kill();
      timeline.current = null;
    };
  }, [reduced]);

  return (
    <figure ref={root} className="sep-figure">
      <svg className="sep-svg" viewBox="-40 0 720 340" role="img" aria-labelledby="sep-caption">
        <defs>
          <clipPath id="sep-clip-l">
            <path d={leftClip} />
          </clipPath>
          <clipPath id="sep-clip-r">
            <path d={rightClip} />
          </clipPath>
        </defs>

        {/* Row-level security, revealed in the gap at the end */}
        <line className="sep-barrier" x1="320" y1="74" x2="320" y2="246" />
        <text className="sep-barrier-label" x="320" y="290" textAnchor="middle">
          {t("security.figure.gate")}
        </text>

        {/* The shared table, drawn twice and clipped along the crack */}
        {(["l", "r"] as const).map((side) => (
          <g key={side} className={`sep-half sep-half-${side}`} clipPath={`url(#sep-clip-${side})`}>
            <rect className="sep-slab" x={SLAB.x} y={SLAB.y} width={SLAB.w} height={SLAB.h} rx="12" />
            <path className="sep-edge" d={crackPath} />
          </g>
        ))}
        <text className="sep-table-name" x={ROW_X - 4} y={SLAB.y + 26}>
          users
        </text>
        <Title x={FINAL_A - 4} label={t("security.figure.companyA")} company="a" />
        <Title x={FINAL_B - 4} label={t("security.figure.companyB")} company="b" />

        {/* Rows, mixed while the table is whole */}
        {ROWS.map((row, i) => {
          const y = ROW_Y0 + i * ROW_STEP;
          return (
            <g key={i} className="sep-row">
              <circle className={`sep-dot-${row.company}`} cx={ROW_X} cy={y} r="4.5" />
              <rect className="sep-row-bar" x={ROW_X + 14} y={y - 4} width={row.width} height="8" rx="4" />
            </g>
          );
        })}

        <path className="sep-crack" d={crackPath} pathLength={1} />
        {SHARDS.map(([x, y, size], i) => (
          <path
            key={i}
            className="sep-shard"
            d={`M${x} ${y} l${i % 2 ? size : -size} ${-size * 0.6} l${i % 2 ? -size * 0.3 : size * 0.4} ${size * 1.3} z`}
          />
        ))}

        <Hand side="l" />
        <Hand side="r" />
      </svg>
      <figcaption>
        <span id="sep-caption">{t("security.figure.caption")}</span>
        {!reduced ? (
          <button type="button" className="sep-replay" onClick={() => timeline.current?.restart()}>
            <IconRefresh width={14} height={14} />
            {t("security.figure.replay")}
          </button>
        ) : null}
      </figcaption>
    </figure>
  );
}

function Title({ x, label, company }: { x: number; label: string; company: Company }) {
  return (
    <g className="sep-title">
      <circle className={`sep-dot-${company}`} cx={x + 4} cy={SLAB.y + 21} r="4.5" />
      <text className="sep-title-text" x={x + 16} y={SLAB.y + 26}>
        {label}
      </text>
    </g>
  );
}

/**
 * A gloved hand gripping the slab's edge: back of the hand outside, four fingers curled
 * over onto the front face. The right hand is the left one mirrored. The cuff carries
 * the company's colour.
 */
function Hand({ side }: { side: "l" | "r" }) {
  const mirror = side === "r" ? "matrix(-1 0 0 1 640 0)" : undefined;
  return (
    <g className={`sep-hand sep-hand-${side}`}>
      <g transform={mirror}>
        <g className="sep-strain">
          <path d="M18 112 q-10 -8 -22 -6" />
          <path d="M8 160 h-24" />
          <path d="M18 208 q-10 8 -22 6" />
        </g>
        <rect className="sep-sleeve" x="-90" y="138" width="138" height="44" rx="10" />
        <rect className={`sep-cuff sep-cuff-${side === "l" ? "a" : "b"}`} x="38" y="134" width="14" height="52" rx="5" />
        <path className="sep-glove" d="M50 128 H96 a26 26 0 0 1 26 26 v12 a26 26 0 0 1 -26 26 H50 Z" />
        <rect className="sep-glove sep-finger" x="104" y="129" width="42" height="15" rx="7.5" />
        <rect className="sep-glove sep-finger" x="106" y="145" width="48" height="15" rx="7.5" />
        <rect className="sep-glove sep-finger" x="106" y="161" width="45" height="15" rx="7.5" />
        <rect className="sep-glove sep-finger" x="104" y="177" width="36" height="14" rx="7" />
      </g>
    </g>
  );
}
