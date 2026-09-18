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
    <form className="form" onSubmit={onSubmit}>
      <label className="field">
        <span>Company name</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="organization"
          placeholder="Acme Inc"
          required
        />
      </label>
      <label className="field">
        <span>Email domain</span>
        <input
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="acme.com"
          autoComplete="off"
          spellCheck={false}
          required
        />
        <small>
          People sign in with Google using this domain. Use <code>gmail.com</code> for a
          personal demo.
        </small>
      </label>
      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
        {pending ? "Creating…" : "Register company"}
      </button>
    </form>
  );
}
