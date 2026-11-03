import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { LanguageProvider } from "./i18n";
import PrivacyPage from "./PrivacyPage";
// Fonts are bundled and served from our own origin, so no visitor IP goes to Google Fonts.
import "@fontsource/schibsted-grotesk/latin-400.css";
import "@fontsource/schibsted-grotesk/latin-500.css";
import "@fontsource/schibsted-grotesk/latin-600.css";
import "@fontsource/schibsted-grotesk/latin-700.css";
import "./styles.css";

// The one public page outside the app. The backend serves index.html for any path.
const isPrivacy = /^\/(privacy|personvern)\/?$/.test(window.location.pathname);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LanguageProvider>
      {isPrivacy ? <PrivacyPage /> : <App />}
    </LanguageProvider>
  </StrictMode>
);
