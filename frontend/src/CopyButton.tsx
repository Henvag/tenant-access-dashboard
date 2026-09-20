import { useEffect, useState } from "react";
import { useLang } from "./i18n";
import { IconCheck, IconCopy } from "./Icons";

export default function CopyButton({ value, label }: { value: string; label?: string }) {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timer);
  }, [copied]);

  return (
    <button
      type="button"
      className={copied ? "btn btn-ghost btn-copy copied" : "btn btn-ghost btn-copy"}
      onClick={() => {
        void navigator.clipboard.writeText(value).then(() => setCopied(true));
      }}
      aria-label={label ?? t("apps.copy")}
    >
      {copied ? <IconCheck width={14} height={14} /> : <IconCopy width={14} height={14} />}
      {copied ? t("apps.copied") : t("apps.copy")}
    </button>
  );
}
