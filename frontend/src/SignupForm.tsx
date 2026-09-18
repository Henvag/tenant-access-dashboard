import { FormEvent, useState } from "react";
import { createTenant } from "./api";

type Props = {
  onCreated: (domain: string) => void;
};

export default function SignupForm({ onCreated }: Props) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const tenant = await createTenant(name, domain);
      onCreated(tenant.workspace_domain);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create company");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel" onSubmit={onSubmit}>
      <h2>Register a company</h2>
      <p className="lede">
        Employees sign in with Google. The first person whose email matches this
        domain becomes admin. For a personal Gmail demo, use gmail.com.
      </p>
      <label>
        Company name
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="organization"
          required
        />
      </label>
      <label>
        Google Workspace domain
        <input
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="gmail.com"
          autoComplete="off"
          required
        />
      </label>
      {error ? <p className="banner error">{error}</p> : null}
      <button type="submit" disabled={pending}>
        {pending ? "Creating…" : "Create tenant"}
      </button>
    </form>
  );
}
