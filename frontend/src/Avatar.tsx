import { initials } from "./format";

type Props = {
  name: string | null;
  email: string;
  size?: "sm" | "md" | "lg";
};

export default function Avatar({ name, email, size = "md" }: Props) {
  return (
    <span
      className={`avatar avatar-${size}`}
      aria-hidden="true"
      title={name ?? email}
    >
      {initials(name, email)}
    </span>
  );
}
