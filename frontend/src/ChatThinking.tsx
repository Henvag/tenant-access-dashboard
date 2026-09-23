import { useEffect, useState } from "react";
import { TKey, useLang } from "./i18n";

const PHASES: TKey[] = ["chat.thinking", "chat.reading", "chat.writing"];

type Props = {
  active: boolean;
};

export default function ChatThinking({ active }: Props) {
  const { t } = useLang();
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!active) {
      setPhase(0);
      return;
    }
    const id = window.setInterval(() => {
      setPhase((current) => (current + 1) % PHASES.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, [active]);

  if (!active) return null;

  return (
    <div className="agent-bubble thinking" aria-live="polite" aria-busy="true">
      <span className="thinking-label">{t(PHASES[phase])}</span>
      <span className="thinking-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}
