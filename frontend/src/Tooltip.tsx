import { ReactNode } from "react";

type Props = {
  label: string;
  children: ReactNode;
  place?: "top" | "bottom";
  className?: string;
};

/**
 * CSS-only tooltip. Shows on hover and keyboard focus, with a short delay.
 * Content comes from `data-tip`, so it works without extra DOM or JS.
 */
export default function Tip({ label, children, place = "top", className }: Props) {
  return (
    <span className={className ? `tip ${className}` : "tip"} data-tip={label} data-place={place}>
      {children}
    </span>
  );
}
