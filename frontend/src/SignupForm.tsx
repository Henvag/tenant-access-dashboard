import { FormEvent, useRef, useState } from "react";
import { loginUrl, Provider } from "./api";
import { useLang } from "./i18n";
import { IconGoogle, IconMicrosoft } from "./Icons";

/** Register by signing in: the company is created for the domain of the
 * email Google or Microsoft verifies, so nobody can claim a domain they
 * cannot sign in with. */
export default function SignupForm() {
  const { t } = useLang();
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const provider = useRef<Provider>("google");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const company = name.trim();
    if (!company) return;
    setPending(true);
    window.location.assign(loginUrl(provider.current, company));
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
          maxLength={200}
          required
        />
        <small>{t("form.signupHelp")}</small>
      </label>
      <div className="signin-actions">
        <button
          type="submit"
          className="btn btn-google btn-block"
          disabled={pending}
          onClick={() => {
            provider.current = "google";
          }}
        >
          <IconGoogle />
          {t("form.registerGoogle")}
        </button>
        <button
          type="submit"
          className="btn btn-microsoft btn-block"
          disabled={pending}
          onClick={() => {
            provider.current = "microsoft";
          }}
        >
          <IconMicrosoft />
          {t("form.registerMicrosoft")}
        </button>
      </div>
    </form>
  );
}
