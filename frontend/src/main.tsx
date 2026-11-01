import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { LanguageProvider } from "./i18n";
import PrivacyPage from "./PrivacyPage";
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
