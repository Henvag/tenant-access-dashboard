import { initials } from "./format";

type Props = {
  name: string | null;
  email: string;
  size?: "sm" | "md" | "lg";
};

const PALETTE = ["teal", "indigo", "amber", "rose", "sky", "violet"] as const;

function hueFor(seed: string): (typeof PALETTE)[number] {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

export default function Avatar({ name, email, size = "md" }: Props) {
  return (
    <span
      className={`avatar avatar-${size} tone-${hueFor(email)}`}
      aria-hidden="true"
      title={name ?? email}
    >
      {initials(name, email)}
    </span>
  );
}
