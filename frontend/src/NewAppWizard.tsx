import { FormEvent, useEffect, useState } from "react";
import {
  APP_CATALOG,
  AppTemplate,
  AppTemplateId,
  normalizeBaseUrl,
  templateById,
  urlsFromTemplate,
} from "./appCatalog";
import { AccessPolicy, AppInput } from "./api";
import AppMark from "./AppMark";
import { messageForApiError } from "./format";
import { TKey, useLang } from "./i18n";
import { IconPlug } from "./Icons";

const POLICY_LABEL: Record<AccessPolicy, TKey> = {
  everyone: "policy.everyone",
  admins: "policy.admins",
  assigned: "policy.assigned",
};

const POLICY_HINT: Record<AccessPolicy, TKey> = {
  everyone: "policy.everyoneHint",
  admins: "policy.adminsHint",
  assigned: "policy.assignedHint",
};

type Props = {
  tenantName: string;
  onCancel: () => void;
  onSubmit: (input: AppInput, templateId: AppTemplateId) => Promise<void>;
};

/**
 * Two-step create flow: pick a catalog template, then configure URLs + policy.
 */
export default function NewAppWizard({ tenantName, onCancel, onSubmit }: Props) {
  const { lang, t } = useLang();
  const [step, setStep] = useState<"pick" | "configure">("pick");
  const [templateId, setTemplateId] = useState<AppTemplateId | null>(null);

  if (step === "pick" || !templateId) {
    return (
      <div className="catalog-pick">
        <p className="hint catalog-pick-hint">{t("catalog.pickHint")}</p>
        <div className="catalog-grid" role="list">
          {APP_CATALOG.map((item) => (
            <button
              key={item.id}
              type="button"
              className="catalog-card"
              role="listitem"
              onClick={() => {
                setTemplateId(item.id);
                setStep("configure");
              }}
            >
              <AppMark name={item.markName} />
              <strong>{t(item.titleKey)}</strong>
              <span className="catalog-card-body">{t(item.bodyKey)}</span>
              <span className="catalog-card-path">{t(item.pathHintKey)}</span>
            </button>
          ))}
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            {t("apps.cancel")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <ConfigureForm
      tenantName={tenantName}
      template={templateById(templateId)}
      onBack={() => {
        setStep("pick");
        setTemplateId(null);
      }}
      onCancel={onCancel}
      onSubmit={(input) => onSubmit(input, templateId)}
      lang={lang}
      t={t}
    />
  );
}

function ConfigureForm({
  tenantName,
  template,
  onBack,
  onCancel,
  onSubmit,
  lang,
  t,
}: {
  tenantName: string;
  template: AppTemplate;
  onBack: () => void;
  onCancel: () => void;
  onSubmit: (input: AppInput) => Promise<void>;
  lang: "en" | "no";
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}) {
  const guided = template.redirectPath !== null;
  const [name, setName] = useState(template.defaultName);
  const [baseUrl, setBaseUrl] = useState("");
  const [redirects, setRedirects] = useState("");
  const [launchUrl, setLaunchUrl] = useState("");
  const [policy, setPolicy] = useState<AccessPolicy>("everyone");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(!guided);

  useEffect(() => {
    if (!guided) return;
    const { redirect, launch } = urlsFromTemplate(template, baseUrl);
    setRedirects(redirect);
    setLaunchUrl(launch);
  }, [baseUrl, guided, template]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      let redirectList = redirects
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      let launch = launchUrl.trim() || null;

      if (guided && !advanced) {
        const base = normalizeBaseUrl(baseUrl);
        if (!base) {
          setError(messageForApiError("domain_url", lang));
          setPending(false);
          return;
        }
        const derived = urlsFromTemplate(template, base);
        redirectList = derived.redirect ? [derived.redirect] : [];
        launch = derived.launch || null;
      }

      await onSubmit({
        name: name.trim(),
        redirect_uris: redirectList,
        launch_url: launch,
        access_policy: policy,
      });
    } catch (err) {
      setError(messageForApiError(err instanceof Error ? err.message : "generic", lang));
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="app-form">
      <div className="catalog-config-head">
        <AppMark name={template.markName} size="sm" />
        <div>
          <strong>{t(template.titleKey)}</strong>
          <p className="hint">{t(template.pathHintKey)}</p>
        </div>
      </div>

      {error ? (
        <p className="banner error" role="alert">
          {error}
        </p>
      ) : null}

      <label className="field">
        <span>{t("apps.nameLabel")}</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={template.defaultName || "My app"}
          maxLength={120}
          required
        />
      </label>

      {guided ? (
        <label className="field">
          <span>{t("catalog.baseUrl")}</span>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={t("catalog.baseUrlPlaceholder")}
            type="url"
            required={!advanced}
            spellCheck={false}
          />
          <small>{t("catalog.baseUrlHint")}</small>
        </label>
      ) : null}

      {(advanced || !guided) && (
        <>
          <label className="field">
            <span>{t("apps.redirects")}</span>
            <textarea
              value={redirects}
              onChange={(e) => setRedirects(e.target.value)}
              placeholder="https://app.example.com/oauth/callback"
              rows={3}
              required
              spellCheck={false}
            />
            <small>{t("apps.redirectsHint")}</small>
          </label>
          <label className="field">
            <span>{t("apps.launchUrl")}</span>
            <input
              value={launchUrl}
              onChange={(e) => setLaunchUrl(e.target.value)}
              placeholder="https://app.example.com"
              type="url"
            />
            <small>{t("apps.launchUrlHint")}</small>
          </label>
        </>
      )}

      {guided ? (
        <button
          type="button"
          className="link catalog-advanced"
          onClick={() => setAdvanced((v) => !v)}
        >
          {advanced ? t("catalog.hideUrls") : t("catalog.showUrls")}
        </button>
      ) : null}

      <fieldset className="field policy-field">
        <legend>{t("apps.policy")}</legend>
        {(["everyone", "admins", "assigned"] as AccessPolicy[]).map((value) => (
          <label key={value} className={policy === value ? "radio-card active" : "radio-card"}>
            <input
              type="radio"
              name="policy"
              value={value}
              checked={policy === value}
              onChange={() => setPolicy(value)}
            />
            <span className="radio-card-text">
              <strong>{t(POLICY_LABEL[value])}</strong>
              <small>{t(POLICY_HINT[value], { tenant: tenantName })}</small>
            </span>
          </label>
        ))}
      </fieldset>

      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onBack} disabled={pending}>
          {t("catalog.back")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={pending}>
          {t("apps.cancel")}
        </button>
        <button type="submit" className="btn btn-primary" disabled={pending}>
          {pending ? t("apps.creating") : t("apps.create")}
        </button>
      </div>
    </form>
  );
}

/** Compact catalog strip for the empty Apps state. */
export function CatalogEmptyCta({ onPick }: { onPick: () => void }) {
  const { t } = useLang();
  return (
    <div className="empty catalog-empty">
      <div className="empty-art" aria-hidden="true">
        <IconPlug width={22} height={22} />
      </div>
      <h3>{t("apps.emptyTitle")}</h3>
      <p>{t("apps.emptyBody")}</p>
      <div className="catalog-grid catalog-grid-compact" role="list">
        {APP_CATALOG.map((item) => (
          <button
            key={item.id}
            type="button"
            className="catalog-card catalog-card-compact"
            role="listitem"
            onClick={onPick}
          >
            <AppMark name={item.markName} size="sm" />
            <strong>{t(item.titleKey)}</strong>
          </button>
        ))}
      </div>
      <button type="button" className="btn btn-primary" onClick={onPick}>
        {t("catalog.emptyCta")}
      </button>
    </div>
  );
}
