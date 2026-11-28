import grafanaLogo from "./assets/grafana.png";
import outlineLogo from "./assets/outline.png";
import portainerLogo from "./assets/portainer.svg";
import giteaLogo from "./assets/gitea.svg";
import bookstackLogo from "./assets/bookstack.svg";
import slackLogo from "./assets/slack.svg";
import openidLogo from "./assets/openid.svg";
import samlLogo from "./assets/saml.png";
import { IconPlug } from "./Icons";

const KNOWN_LOGOS: { match: RegExp; src: string; alt: string }[] = [
  { match: /grafana/i, src: grafanaLogo, alt: "Grafana" },
  { match: /outline/i, src: outlineLogo, alt: "Outline" },
  { match: /portainer/i, src: portainerLogo, alt: "Portainer" },
  { match: /gitea/i, src: giteaLogo, alt: "Gitea" },
  { match: /bookstack/i, src: bookstackLogo, alt: "BookStack" },
  { match: /slack/i, src: slackLogo, alt: "Slack" },
  // Catalog cards for the custom app types.
  { match: /^openid connect$/i, src: openidLogo, alt: "OpenID Connect" },
  { match: /^saml$/i, src: samlLogo, alt: "SAML" },
];

/** Apps we don't know by name still show how people sign in to them. */
const PROTOCOL_LOGOS: Record<"oidc" | "saml", string> = {
  oidc: openidLogo,
  saml: samlLogo,
};

type Props = {
  name: string;
  /** Visual size of the mark container. */
  size?: "sm" | "md";
  /** How people sign in to the app; picks a logo when the name isn't a known product. */
  protocol?: "oidc" | "saml" | null;
};

/**
 * App glyph for lists and tiles. Known products get their logo;
 * other apps show their sign-in protocol (OpenID Connect or SAML), and
 * anything else falls back to the generic plug icon.
 */
export default function AppMark({ name, size = "md", protocol }: Props) {
  const known = KNOWN_LOGOS.find((entry) => entry.match.test(name));
  const className = size === "sm" ? "app-mark app-mark-sm" : "app-mark";
  const src = known?.src ?? (protocol ? PROTOCOL_LOGOS[protocol] : undefined);

  if (src) {
    return (
      <span className={`${className} app-mark-brand`} aria-hidden="true">
        <img src={src} alt="" />
      </span>
    );
  }

  return (
    <span className={className} aria-hidden="true">
      <IconPlug width={size === "sm" ? 16 : 18} height={size === "sm" ? 16 : 18} />
    </span>
  );
}
