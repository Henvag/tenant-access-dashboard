import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  role: "user" | "assistant";
  content: string;
};

/** Soften characters that look broken in a chat bubble. */
function tidy(text: string): string {
  return text
    .replace(/\u2014/g, "-")
    .replace(/\u2013/g, "-")
    .replace(/\u00a0/g, " ");
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
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          // Keep headings readable inside a bubble.
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
