type Props = {
  label: string;
  value: string | number;
  hint?: string;
};

/** One cell of the overview figures strip: label over number, no icon. */
export default function StatCard({ label, value, hint }: Props) {
  return (
    <div className="stat">
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {hint ? <span className="stat-hint">{hint}</span> : null}
      </div>
    </div>
  );
}
