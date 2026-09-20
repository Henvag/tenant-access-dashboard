import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { IconMore, IconRefresh } from "./Icons";

export type MenuItem = {
  key: string;
  label: string;
  danger?: boolean;
  onSelect: () => void;
};

type Props = {
  items: MenuItem[];
  busy?: boolean;
  label: string;
};

/**
 * Compact "⋯" menu. The list is position:fixed so it is never clipped by a
 * scroll container; it closes on outside click, Escape, scroll or resize.
 */
export default function RowMenu({ items, busy = false, label }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    if (!open || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onPointer = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <div className="menu" ref={wrapRef}>
      <button
        ref={buttonRef}
        type="button"
        className="btn-icon"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        disabled={busy}
        onClick={() => setOpen((value) => !value)}
      >
        {busy ? (
          <IconRefresh width={15} height={15} className="spin" />
        ) : (
          <IconMore width={16} height={16} />
        )}
      </button>
      {open && pos ? (
        <div className="menu-list" role="menu" style={{ top: pos.top, right: pos.right }}>
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              role="menuitem"
              className={item.danger ? "menu-item danger" : "menu-item"}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
