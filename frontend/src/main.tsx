import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import App, { hasEntryState, rememberedSignedIn } from "./App";
import { detectLang, LanguageProvider } from "./i18n";
import NotFoundPage from "./NotFoundPage";
import PrivacyPage from "./PrivacyPage";
import { matchPage } from "./routes";
// Fonts are bundled and served from our own origin, so no visitor IP goes to Google Fonts.
import "@fontsource/schibsted-grotesk/latin-400.css";
import "@fontsource/schibsted-grotesk/latin-500.css";
import "@fontsource/schibsted-grotesk/latin-600.css";
import "@fontsource/schibsted-grotesk/latin-700.css";
import "./styles.css";

// The public pages have one address per language (see routes.ts). Any other path the
// backend sends here is its 404 page.
const match = matchPage(window.location.pathname);
const page = match ? (match.page === "privacy" ? <PrivacyPage /> : <App />) : <NotFoundPage />;

const tree = (
  <StrictMode>
    <LanguageProvider initialLang={match?.lang}>{page}</LanguageProvider>
  </StrictMode>
);

const container = document.getElementById("root")!;

// The HTML already holds the page as the build drew it (scripts/prerender.mjs). Hydrate
// when the first render will draw the same thing; otherwise draw from scratch.
const sameAsPrerendered =
  container.hasChildNodes() &&
  (match
    ? match.page !== "home" || (!rememberedSignedIn() && !hasEntryState())
    : detectLang() === "en"); // 404.html is drawn in English

if (sameAsPrerendered) {
  hydrateRoot(container, tree);
} else {
  createRoot(container).render(tree);
}
