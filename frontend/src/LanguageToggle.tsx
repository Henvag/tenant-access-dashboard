import { Lang, useLang } from "./i18n";

const OPTIONS: { value: Lang; label: string; titleKey: "lang.en" | "lang.no" }[] = [
  { value: "en", label: "EN", titleKey: "lang.en" },
  { value: "no", label: "NO", titleKey: "lang.no" },
];

type Props = {
  variant?: "light" | "dark";
};

export default function LanguageToggle({ variant = "light" }: Props) {
  const { lang, setLang, t } = useLang();

  return (
    <div
      className={`lang-toggle lang-toggle-${variant}`}
      role="group"
      aria-label={t("lang.label")}
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={lang === option.value ? "lang-opt active" : "lang-opt"}
          onClick={() => setLang(option.value)}
          aria-pressed={lang === option.value}
          title={t(option.titleKey)}
          lang={option.value === "no" ? "nb" : "en"}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
