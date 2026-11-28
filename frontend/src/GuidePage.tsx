import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import BrandMark from "./BrandMark";
import { Guide, GUIDES, GUIDES_INDEX, GUIDES_PATH, guidePath } from "./guides";
import { pagePath } from "./routes";

/** A Norwegian guide, or the list of guides when guide is null. Norwegian only. */
export default function GuidePage({ guide }: { guide: Guide | null }) {
  const home = pagePath("home", "no");
  return (
    <main className="legal">
      <header className="legal-top">
        <a className="brand legal-brand" href={home}>
          <BrandMark size={28} />
          <span className="brand-name">Tenant Access</span>
        </a>
      </header>

      <article className="legal-body guide" lang="nb">
        {guide ? (
          <>
            <p className="guide-crumb">
              <a href={GUIDES_PATH}>Guider</a>
            </p>
            <h1>{guide.title}</h1>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) =>
                  href && /^https?:/.test(href) ? (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ) : (
                    <a href={href}>{children}</a>
                  ),
              }}
            >
              {guide.body}
            </ReactMarkdown>
          </>
        ) : (
          <>
            <h1>{GUIDES_INDEX.title}</h1>
            <p className="legal-lead">{GUIDES_INDEX.description}</p>
            <ul className="guide-list">
              {GUIDES.map((g) => (
                <li key={g.slug}>
                  <a href={guidePath(g)}>{g.title}</a>
                  <p>{g.description}</p>
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="legal-back">
          <a href={home}>Tilbake til Tenant Access</a>
        </p>
      </article>
    </main>
  );
}
