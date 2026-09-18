import { ReactNode } from "react";

type Props = {
  label: string;
  value: string | number;
  hint?: string;
  icon: ReactNode;
  tone?: "default" | "accent" | "warm";
};

export default function StatCard({ label, value, hint, icon, tone = "default" }: Props) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {hint ? <span className="stat-hint">{hint}</span> : null}
      </div>
    </div>
  );
}
