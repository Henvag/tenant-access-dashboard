import grafanaLogo from "./assets/grafana.png";
import outlineLogo from "./assets/outline.svg";
import { IconPlug } from "./Icons";

const KNOWN_LOGOS: { match: RegExp; src: string; alt: string }[] = [
  { match: /grafana/i, src: grafanaLogo, alt: "Grafana" },
  { match: /outline/i, src: outlineLogo, alt: "Outline" },
];

type Props = {
  name: string;
  /** Visual size of the mark container. */
  size?: "sm" | "md";
};

/**
 * App glyph for lists and tiles. Known products get their logo;
 * everything else falls back to the generic plug icon.
 */
export default function AppMark({ name, size = "md" }: Props) {
  const known = KNOWN_LOGOS.find((entry) => entry.match.test(name));
  const className = size === "sm" ? "app-mark app-mark-sm" : "app-mark";

  if (known) {
    return (
      <span className={`${className} app-mark-brand`} aria-hidden="true">
        <img src={known.src} alt="" />
      </span>
    );
  }

  return (
    <span className={className} aria-hidden="true">
      <IconPlug width={size === "sm" ? 16 : 18} height={size === "sm" ? 16 : 18} />
    </span>
  );
}
