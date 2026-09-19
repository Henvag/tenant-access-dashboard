import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "en" | "no";

const STORAGE_KEY = "tenant-access.lang";

const en = {
  "app.loading": "Loading your workspace…",
  "brand": "Tenant Access",

  "landing.title": "See who has access to your company, in one place.",
  "landing.lede":
    "Register your company, let employees sign in with Google or Microsoft, and give admins a clear view of everyone in the tenant. Each company's data is isolated at the database level.",
  "feature.google.title": "Google & Microsoft sign-in",
  "feature.google.body": "OIDC against Google Workspace or Entra ID. No passwords to manage.",
  "feature.isolated.title": "Isolated per tenant",
  "feature.isolated.body": "Postgres row-level security keeps companies apart.",
  "feature.roles.title": "Admin and member roles",
  "feature.roles.body": "The first person from a domain becomes admin.",

  "tabs.label": "Get started",
  "tabs.signin": "Sign in",
  "tabs.register": "Register company",
  "signin.title": "Welcome back",
  "signin.hint": "Use an account on your company's registered email domain.",
  "signin.google": "Continue with Google",
  "signin.microsoft": "Continue with Microsoft",
  "signin.new": "New company?",
  "signin.registerFirst": "Register it first",
  "register.title": "Register your company",
  "register.hint": "Takes ten seconds. Then sign in with Google or Microsoft to become admin.",
  "notice.registered": "{domain} is registered. Sign in with a @{domain} account.",

  "form.company": "Company name",
  "form.companyPlaceholder": "Acme Inc",
  "form.domain": "Email domain",
  "form.domainHelpBefore": "People sign in with Google or Microsoft using this domain. Demo domains:",
  "form.domainHelpAfter": ".",
  "form.submit": "Register company",
  "form.pending": "Creating…",
  "form.error": "Could not create company",

  "nav.label": "Main",
  "nav.overview": "Overview",
  "nav.people": "People",
  "nav.audit": "Audit",
  "sidebar.tenant": "Tenant",
  "role.admin": "Admin",
  "role.member": "Member",
  "signout": "Sign out",
  "lang.label": "Language",

  "search.placeholder": "Search name or email",
  "refresh": "Refresh",

  "stats.people": "People",
  "stats.peopleHint": "Signed in at least once",
  "stats.admins": "Admins",
  "stats.adminsHint": "Can view this dashboard",
  "stats.members": "Members",
  "stats.membersHint": "Regular access",
  "stats.active": "Active this week",
  "stats.activeHint": "Signed in within 7 days",

  "recent.title": "Recent activity",
  "recent.hint": "Latest sign-ins for @{domain}",
  "recent.viewAll": "View audit log →",
  "recent.emptyTitle": "No sign-ins yet",
  "recent.emptyBody": "Sign-ins appear here as people authenticate with Google or Microsoft.",

  "people.title": "Everyone in {tenant}",
  "people.count": "{shown} of {total} shown · isolated to your tenant",
  "filter.label": "Filter by role",
  "filter.all": "All",
  "filter.admins": "Admins",
  "filter.members": "Members",
  "people.noMatches": "No matches",
  "people.noMatchesBody": "Try a different search or clear the role filter.",
  "people.emptyTitle": "No people yet",
  "people.emptyBody": "Everyone who signs in with a matching account will appear here.",

  "audit.title": "Sign-in audit",
  "audit.hint": "{count} events · isolated to your tenant",
  "audit.event": "Event",
  "audit.idp": "Identity provider",
  "audit.detail": "Detail",
  "audit.ip": "IP",
  "audit.when": "When",
  "audit.login": "Sign-in",
  "audit.loginFailed": "Failed sign-in",
  "audit.failedUnknown": "Sign-in failed",
  "audit.noDetail": "—",
  "audit.emptyTitle": "No audit events yet",
  "audit.emptyBody": "Successful and failed sign-ins for your domain are recorded here.",
  "idp.google": "Google",
  "idp.microsoft": "Microsoft",

  "table.person": "Person",
  "table.role": "Role",
  "table.activity": "Activity",
  "table.lastSignin": "Last sign-in",
  "table.you": "You",
  "activity.never": "Never signed in",
  "activity.active": "Active",
  "activity.recent": "Recent",
  "activity.inactive": "Inactive",

  "time.never": "Never",
  "time.unknown": "Unknown",
  "time.justNow": "Just now",

  "member.title": "You're signed in",
  "member.body":
    "Member of {tenant}. Only admins can see the full list of people. Last sign-in: {time}.",
  "error.loadPeople": "Could not load people",
  "error.loadAudit": "Could not load audit log",
  "error.load_people": "Could not load people",
  "error.generic": "Something went wrong. Try again.",
  "error.tenant_exists": "A company is already registered for that email domain.",
  "error.name_required": "Company name is required.",
  "error.domain_url": "Enter a domain like acme.com, not a URL.",
  "error.domain_invalid": "That email domain is not valid.",
  "error.not_signed_in": "Not signed in.",
  "error.admin_required": "Admin role required.",

  "auth.no_tenant":
    "No company is registered for your email domain yet. Register it first, then sign in.",
  "auth.invalid_domain": "That email domain is not valid.",
  "auth.domain_mismatch": "Your Google account domain does not match this Workspace.",
  "auth.missing_claims": "Sign-in did not return a verified email. Try again.",
  "auth.unverified_email": "Your email is not verified.",
  "auth.identity_conflict": "This email is already linked to a different identity.",
  "auth.oidc_failed": "Sign-in failed. Try again.",
  "auth.generic": "Sign-in error: {code}",
} as const;

export type TKey = keyof typeof en;

const no: Record<TKey, string> = {
  "app.loading": "Laster arbeidsområdet ditt…",
  "brand": "Tenant Access",

  "landing.title": "Se hvem som har tilgang i selskapet ditt, på ett sted.",
  "landing.lede":
    "Registrer selskapet, la ansatte logge inn med Google eller Microsoft, og gi administratorer full oversikt over alle i tenanten. Hvert selskaps data er isolert på databasenivå.",
  "feature.google.title": "Google- og Microsoft-innlogging",
  "feature.google.body": "OIDC mot Google Workspace eller Entra ID. Ingen passord å administrere.",
  "feature.isolated.title": "Isolert per tenant",
  "feature.isolated.body": "Postgres row-level security holder selskapene adskilt.",
  "feature.roles.title": "Admin- og medlemsroller",
  "feature.roles.body": "Den første fra et domene blir administrator.",

  "tabs.label": "Kom i gang",
  "tabs.signin": "Logg inn",
  "tabs.register": "Registrer selskap",
  "signin.title": "Velkommen tilbake",
  "signin.hint": "Bruk en konto på selskapets registrerte e-postdomene.",
  "signin.google": "Fortsett med Google",
  "signin.microsoft": "Fortsett med Microsoft",
  "signin.new": "Nytt selskap?",
  "signin.registerFirst": "Registrer det først",
  "register.title": "Registrer selskapet ditt",
  "register.hint": "Tar ti sekunder. Logg deretter inn med Google eller Microsoft for å bli administrator.",
  "notice.registered": "{domain} er registrert. Logg inn med en @{domain}-konto.",

  "form.company": "Selskapsnavn",
  "form.companyPlaceholder": "Acme AS",
  "form.domain": "E-postdomene",
  "form.domainHelpBefore": "Ansatte logger inn med Google eller Microsoft via dette domenet. Demo-domener:",
  "form.domainHelpAfter": ".",
  "form.submit": "Registrer selskap",
  "form.pending": "Oppretter…",
  "form.error": "Kunne ikke opprette selskap",

  "nav.label": "Hovedmeny",
  "nav.overview": "Oversikt",
  "nav.people": "Personer",
  "nav.audit": "Revisjonslogg",
  "sidebar.tenant": "Tenant",
  "role.admin": "Administrator",
  "role.member": "Medlem",
  "signout": "Logg ut",
  "lang.label": "Språk",

  "search.placeholder": "Søk på navn eller e-post",
  "refresh": "Oppdater",

  "stats.people": "Personer",
  "stats.peopleHint": "Har logget inn minst én gang",
  "stats.admins": "Administratorer",
  "stats.adminsHint": "Kan se dette dashbordet",
  "stats.members": "Medlemmer",
  "stats.membersHint": "Vanlig tilgang",
  "stats.active": "Aktive denne uken",
  "stats.activeHint": "Logget inn siste 7 dager",

  "recent.title": "Siste aktivitet",
  "recent.hint": "Siste innlogginger for @{domain}",
  "recent.viewAll": "Se revisjonslogg →",
  "recent.emptyTitle": "Ingen innlogginger enda",
  "recent.emptyBody": "Innlogginger vises her når noen autentiserer seg med Google eller Microsoft.",

  "people.title": "Alle i {tenant}",
  "people.count": "{shown} av {total} vises · isolert til din tenant",
  "filter.label": "Filtrer etter rolle",
  "filter.all": "Alle",
  "filter.admins": "Administratorer",
  "filter.members": "Medlemmer",
  "people.noMatches": "Ingen treff",
  "people.noMatchesBody": "Prøv et annet søk eller fjern rollefilteret.",
  "people.emptyTitle": "Ingen personer enda",
  "people.emptyBody": "Alle som logger inn med en matchende konto vises her.",

  "audit.title": "Innloggingsrevisjon",
  "audit.hint": "{count} hendelser · isolert til din tenant",
  "audit.event": "Hendelse",
  "audit.idp": "Identitetsleverandør",
  "audit.detail": "Detalj",
  "audit.ip": "IP",
  "audit.when": "Når",
  "audit.login": "Innlogging",
  "audit.loginFailed": "Mislykket innlogging",
  "audit.failedUnknown": "Innlogging feilet",
  "audit.noDetail": "—",
  "audit.emptyTitle": "Ingen revisjonshendelser enda",
  "audit.emptyBody": "Vellykkede og mislykkede innlogginger for domenet ditt lagres her.",
  "idp.google": "Google",
  "idp.microsoft": "Microsoft",

  "table.person": "Person",
  "table.role": "Rolle",
  "table.activity": "Aktivitet",
  "table.lastSignin": "Sist innlogget",
  "table.you": "Deg",
  "activity.never": "Aldri logget inn",
  "activity.active": "Aktiv",
  "activity.recent": "Nylig",
  "activity.inactive": "Inaktiv",

  "time.never": "Aldri",
  "time.unknown": "Ukjent",
  "time.justNow": "Akkurat nå",

  "member.title": "Du er logget inn",
  "member.body":
    "Medlem av {tenant}. Bare administratorer kan se hele personlisten. Sist innlogget: {time}.",
  "error.loadPeople": "Kunne ikke laste personer",
  "error.loadAudit": "Kunne ikke laste revisjonsloggen",
  "error.load_people": "Kunne ikke laste personer",
  "error.generic": "Noe gikk galt. Prøv igjen.",
  "error.tenant_exists": "Et selskap er allerede registrert for det e-postdomenet.",
  "error.name_required": "Selskapsnavn er påkrevd.",
  "error.domain_url": "Skriv inn et domene som acme.com, ikke en URL.",
  "error.domain_invalid": "E-postdomenet er ikke gyldig.",
  "error.not_signed_in": "Ikke innlogget.",
  "error.admin_required": "Administratorrolle kreves.",

  "auth.no_tenant":
    "Ingen selskap er registrert for e-postdomenet ditt enda. Registrer det først, og logg deretter inn.",
  "auth.invalid_domain": "E-postdomenet er ikke gyldig.",
  "auth.domain_mismatch": "Domenet på Google-kontoen stemmer ikke med denne Workspace-tenanten.",
  "auth.missing_claims": "Innlogging returnerte ikke en verifisert e-post. Prøv igjen.",
  "auth.unverified_email": "E-posten din er ikke verifisert.",
  "auth.identity_conflict": "Denne e-posten er allerede knyttet til en annen identitet.",
  "auth.oidc_failed": "Innlogging feilet. Prøv igjen.",
  "auth.generic": "Innloggingsfeil: {code}",
};

const DICTIONARIES: Record<Lang, Record<TKey, string>> = { en, no };

export const LOCALES: Record<Lang, string> = { en: "en", no: "nb" };

type Vars = Record<string, string | number>;

export function translate(lang: Lang, key: TKey, vars?: Vars): string {
  const template = DICTIONARIES[lang][key] ?? DICTIONARIES.en[key] ?? key;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) =>
    name in vars ? String(vars[name]) : `{${name}}`
  );
}

function detectLang(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "no") return stored;
  } catch {
    // ignore storage errors (private mode etc.)
  }
  const browser = (navigator.language || "").toLowerCase();
  return /^(nb|nn|no)\b/.test(browser) ? "no" : "en";
}

type LangContextValue = {
  lang: Lang;
  locale: string;
  setLang: (lang: Lang) => void;
  t: (key: TKey, vars?: Vars) => string;
};

const LangContext = createContext<LangContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang);

  useEffect(() => {
    document.documentElement.lang = LOCALES[lang];
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo<LangContextValue>(
    () => ({
      lang,
      locale: LOCALES[lang],
      setLang,
      t: (key, vars) => translate(lang, key, vars),
    }),
    [lang, setLang]
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): LangContextValue {
  const value = useContext(LangContext);
  if (!value) {
    throw new Error("useLang must be used inside LanguageProvider");
  }
  return value;
}
