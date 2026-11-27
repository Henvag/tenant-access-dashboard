import BrandMark from "./BrandMark";
import { useLang } from "./i18n";
import { pagePath } from "./routes";

/** What the backend's 404 answer shows (prerendered to 404.html). */
export default function NotFoundPage() {
  const { lang, t } = useLang();
  const home = pagePath("home", lang);
  return (
    <main className="legal">
      <header className="legal-top">
        <a className="brand legal-brand" href={home}>
          <BrandMark size={28} />
          <span className="brand-name">{t("brand")}</span>
        </a>
      </header>
      <article className="legal-body">
        <h1>{t("notFound.title")}</h1>
        <p className="legal-lead">{t("notFound.body")}</p>
        <p className="legal-back">
          <a href={home}>{t("notFound.back")}</a>
        </p>
      </article>
    </main>
  );
}
