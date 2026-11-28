import grafanaMicrosoft from "./guides/grafana-innlogging-microsoft-365.md?raw";
import offboarding from "./guides/stenge-tilgang-ansatt-slutter.md?raw";

/**
 * Norwegian how-to guides under /no/guider. Each body is Markdown in src/guides/ and is
 * prerendered to static HTML (scripts/prerender.mjs). Adding one: add the file, add it
 * here, and add its path to backend/app/main.py, cloudflare/edge (worker.js and
 * wrangler.toml) and public/sitemap.xml.
 */
export type Guide = {
  slug: string;
  title: string;
  /** The search-result snippet, and the line under the title on the list page. */
  description: string;
  body: string;
};

export const GUIDES: Guide[] = [
  {
    slug: "stenge-tilgang-ansatt-slutter",
    title: "Sjekkliste: stenge tilgang når en ansatt slutter",
    description:
      "En praktisk sjekkliste for små bedrifter: hva som må stenges i Microsoft 365, på PC-en og i verktøyene dere drifter selv når en ansatt slutter.",
    body: offboarding,
  },
  {
    slug: "grafana-innlogging-microsoft-365",
    title: "Slik setter du opp Grafana-innlogging med Microsoft 365",
    description:
      "Steg for steg: la de ansatte logge inn i Grafana med Microsoft 365-kontoen sin (Microsoft Entra ID), og styr hvem som blir Viewer, Editor og Admin.",
    body: grafanaMicrosoft,
  },
];

export const GUIDES_PATH = "/no/guider";

export const GUIDES_INDEX = {
  title: "Guider",
  description:
    "Praktiske guider på norsk om innlogging, tilgangsstyring og hva som må stenges når noen slutter, for små bedrifter som drifter egne verktøy.",
};

export function guidePath(guide: Guide): string {
  return `${GUIDES_PATH}/${guide.slug}`;
}

/** null: not a guide address. { guide: null }: the list page. */
export function matchGuide(pathname: string): { guide: Guide | null } | null {
  const path = pathname.replace(/\/+$/, "");
  if (path === GUIDES_PATH) return { guide: null };
  const guide = GUIDES.find((g) => guidePath(g) === path);
  return guide ? { guide } : null;
}

export function guideTitle(guide: Guide | null): string {
  return `${guide ? guide.title : GUIDES_INDEX.title} · Tenant Access`;
}
