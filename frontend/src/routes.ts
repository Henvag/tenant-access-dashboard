import type { Lang } from "./i18n";

/**
 * The public pages that have their own address in each language. They are prerendered to
 * static HTML at build time (scripts/prerender.mjs), and the backend answers 404 for any
 * other path that is not a file or an API route.
 */
export type PageId = "home" | "privacy" | "dpa";

export const PAGE_PATHS: Record<PageId, Record<Lang, string>> = {
  home: { en: "/", no: "/no" },
  privacy: { en: "/privacy", no: "/personvern" },
  dpa: { en: "/dpa", no: "/databehandleravtale" },
};

export type PageMatch = { page: PageId; lang: Lang };

export function matchPage(pathname: string): PageMatch | null {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  for (const page of Object.keys(PAGE_PATHS) as PageId[]) {
    for (const lang of Object.keys(PAGE_PATHS[page]) as Lang[]) {
      if (PAGE_PATHS[page][lang] === path) return { page, lang };
    }
  }
  return null;
}

export function pagePath(page: PageId, lang: Lang): string {
  return PAGE_PATHS[page][lang];
}
