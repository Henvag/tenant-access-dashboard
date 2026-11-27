import { StrictMode } from "react";
import { renderToString } from "react-dom/server";
import { Lang, LanguageProvider, pageTitle, translate } from "./i18n";
import Landing from "./Landing";
import NotFoundPage from "./NotFoundPage";
import PrivacyPage, { PRIVACY_COPY } from "./PrivacyPage";
import { PageId } from "./routes";

export { PAGE_PATHS } from "./routes";

/**
 * Build-time entry used by scripts/prerender.mjs. It draws each public page the way the
 * browser's first render draws it, so the browser can hydrate the HTML instead of
 * replacing it.
 */
export function renderPage(page: PageId | "notFound", lang: Lang): string {
  const body =
    page === "home" ? (
      <Landing initialErrorCode={null} denial={null} continueApp={null} inviteToken={null} initialTab="signin" />
    ) : page === "privacy" ? (
      <PrivacyPage />
    ) : (
      <NotFoundPage />
    );
  return renderToString(
    <StrictMode>
      <LanguageProvider initialLang={lang}>{body}</LanguageProvider>
    </StrictMode>,
  );
}

export { pageTitle };

/** The search-result snippet of each page. */
export function pageDescription(page: PageId | "notFound", lang: Lang): string {
  if (page === "privacy") return PRIVACY_COPY[lang].lead;
  if (page === "notFound") return translate(lang, "notFound.body");
  return lang === "no"
    ? "Teamet logger inn med Google eller Microsoft. Du bestemmer hvem som kan åpne Grafana, Outline, Gitea og de andre verktøyene selskapet drifter. Laget for små selskaper, på norsk og engelsk."
    : "Your team signs in with Google or Microsoft. You decide who may open Grafana, Outline, Gitea and the other tools your company hosts. Made for small companies, in English and Norwegian.";
}

/** The one-line summary in link previews. */
export function previewDescription(lang: Lang): string {
  return translate(lang, "landing.title");
}
