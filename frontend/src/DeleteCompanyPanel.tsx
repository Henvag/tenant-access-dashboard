import { FormEvent, useState } from "react";
import { deleteCompany } from "./api";
import { messageForApiError } from "./format";
import { useLang } from "./i18n";
import Modal from "./Modal";

type Props = {
  name: string;
  domain: string;
};

/** Owner only. Typing the company's domain is the confirmation. */
export default function DeleteCompanyPanel({ name, domain }: Props) {
  const { lang, t } = useLang();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const matches = typed.trim().toLowerCase() === domain.toLowerCase();

  function close() {
    if (busy) return;
    setOpen(false);
    setTyped("");
    setError(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!matches || busy) return;
    setBusy(true);
    setError(null);
    try {
      await deleteCompany(typed.trim());
      window.location.assign("/");
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
      setBusy(false);
    }
  }

  return (
    <section className="card danger-card">
      <div className="card-head">
        <div>
          <h2>{t("danger.title")}</h2>
          <p className="hint">{t("danger.hint")}</p>
        </div>
        <button type="button" className="btn btn-danger" onClick={() => setOpen(true)}>
          {t("danger.open")}
        </button>
      </div>

      {open ? (
        <Modal title={t("danger.modalTitle", { name })} hint={t("danger.modalHint")} onClose={close}>
          <form onSubmit={onSubmit}>
            <label className="field">
              <span>{t("danger.confirmLabel", { domain })}</span>
              <input
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                placeholder={domain}
              />
            </label>
            {error ? <p className="banner error">{error}</p> : null}
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={close} disabled={busy}>
                {t("apps.cancel")}
              </button>
              <button type="submit" className="btn btn-danger" disabled={!matches || busy}>
                {busy ? t("danger.working") : t("danger.confirm")}
              </button>
            </div>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}
