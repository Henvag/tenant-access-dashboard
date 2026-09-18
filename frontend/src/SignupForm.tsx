import { FormEvent, useState } from "react";
import { createTenant } from "./api";
import { useLang } from "./i18n";

type Props = {
  onCreated: (domain: string) => void;
};

export default function SignupForm({ onCreated }: Props) {
  const { t } = useLang();
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
      setError(err instanceof Error ? err.message : t("form.error"));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="form" onSubmit={onSubmit}>
      <label className="field">
        <span>{t("form.company")}</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="organization"
          placeholder={t("form.companyPlaceholder")}
          required
        />
      </label>
      <label className="field">
        <span>{t("form.domain")}</span>
        <input
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="acme.com"
          autoComplete="off"
          spellCheck={false}
          required
        />
        <small>
          {t("form.domainHelpBefore")} <code>gmail.com</code> {t("form.domainHelpAfter")}
        </small>
      </label>
      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
        {pending ? t("form.pending") : t("form.submit")}
      </button>
    </form>
  );
}
