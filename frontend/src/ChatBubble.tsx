import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  role: "user" | "assistant";
  content: string;
};

const VIEWS = new Set([
  "overview",
  "ask",
  "people",
  "apps",
  "agents",
  "organization",
  "audit",
  "billing",
]);

/** Soften characters that look broken in a chat bubble. */
function tidy(text: string): string {
  return text
    .replace(/\u2014/g, "-")
    .replace(/\u2013/g, "-")
    .replace(/\u00a0/g, " ");
}

/** Portal deep links like ?view=people or /?view=billing stay in the app. */
export function viewFromHref(href: string | undefined): string | null {
  if (!href) return null;
  try {
    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin) return null;
    if (url.pathname !== "/" && url.pathname !== "") return null;
    const view = url.searchParams.get("view") ?? "overview";
    return VIEWS.has(view) ? view : null;
  } catch {
    return null;
  }
}

function openView(view: string) {
  const url = new URL(window.location.href);
  if (view === "overview") url.searchParams.delete("view");
  else url.searchParams.set("view", view);
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  window.dispatchEvent(new CustomEvent("tenant-access:navigate", { detail: { view } }));
}

export default function ChatBubble({ role, content }: Props) {
  const text = tidy(content);
  if (role === "user") {
    return <p className="agent-bubble me">{text}</p>;
  }

  return (
    <div className="agent-bubble md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const view = viewFromHref(href);
            if (view) {
              return (
                <a
                  href={href}
                  onClick={(event) => {
                    event.preventDefault();
                    openView(view);
                  }}
                >
                  {children}
                </a>
              );
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
          h1: ({ children }) => <p className="md-heading">{children}</p>,
          h2: ({ children }) => <p className="md-heading">{children}</p>,
          h3: ({ children }) => <p className="md-heading">{children}</p>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
