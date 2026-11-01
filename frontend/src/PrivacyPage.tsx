import BrandMark from "./BrandMark";
import { Lang, useLang } from "./i18n";
import LanguageToggle from "./LanguageToggle";

type Row = [string, string];

type Copy = {
  title: string;
  updated: string;
  lead: string;
  back: string;
  roleTitle: string;
  role: string;
  storeTitle: string;
  store: Row[];
  storeNote: string;
  whereTitle: string;
  where: string;
  whoTitle: string;
  whoHead: [string, string, string];
  who: [string, string, string][];
  keepTitle: string;
  keep: string;
  rightsTitle: string;
  rights: string;
};

/*
 * Keep this page true to the running service. If the hosting region, a
 * subprocessor or what the database stores changes, change it here in both
 * languages in the same pull request.
 */
const COPY: Record<Lang, Copy> = {
  en: {
    title: "Privacy and hosting",
    updated: "Last updated 1 November 2026.",
    lead: "What Tenant Access stores, where it is stored, and who else handles it.",
    back: "Back to Tenant Access",
    roleTitle: "Who is responsible",
    role: "Each company that registers decides who joins and which apps they may open. The company is the controller for its people's data. Tenant Access stores and processes that data on the company's behalf.",
    storeTitle: "What we store",
    store: [
      ["Company", "Name, email domain, plan, and a logo if the owner uploads one."],
      ["People", "Name, work email, the account ID from Google or Microsoft, role, last sign-in, and whether the person is switched off."],
      ["Apps", "The apps a company adds, their sign-in settings, and who may open each one. App secrets are stored hashed."],
      ["Audit log", "Every sign-in and app sign-in attempt: time, result, IP address and browser type."],
      ["Billing", "Stripe customer and subscription IDs. Card and Vipps details stay with Stripe."],
      ["Ask and agents", "Only if a company turns them on: its own AI provider key, stored encrypted."],
    ],
    storeNote: "We never see or store passwords. There are no tracking or advertising cookies. One sign-in cookie keeps you signed in and expires after 12 hours.",
    whereTitle: "Where it is stored",
    where: "The service runs on Render and the database on Neon, both in Oregon, USA (AWS us-west-2). Traffic to tenantaccess.me passes through Cloudflare. This means data is stored outside the EU and EEA today.",
    whoTitle: "Who else handles it",
    whoHead: ["Company", "What for", "When"],
    who: [
      ["Render", "Runs the service", "Always"],
      ["Neon", "Hosts the database", "Always"],
      ["Cloudflare", "DNS and network protection", "Always"],
      ["Google, Microsoft", "Confirms who you are at sign-in", "When you sign in with them"],
      ["Stripe", "Card and Vipps payments", "Paying companies only"],
      ["OpenAI, Anthropic or Google", "Answers questions in Ask and agents, with the company details the question needs", "Only if the company adds its own key"],
    ],
    keepTitle: "How long we keep it",
    keep: "People, apps and audit events stay until they are removed. Your plan decides how far back the audit log shows (14, 90 or 365 days), but older events are not deleted. Switching a person off stops every sign-in at once, and the record stays so the audit log still makes sense.",
    rightsTitle: "Seeing, correcting or deleting your data",
    rights: "Ask the owner of your company first. Owners can change your role or switch you off under People. Deleting a person or a whole company is not self-service yet, so the owner has to ask the operator of Tenant Access.",
  },
  no: {
    title: "Personvern og drift",
    updated: "Sist oppdatert 1. november 2026.",
    lead: "Hva Tenant Access lagrer, hvor det lagres, og hvem andre som behandler det.",
    back: "Tilbake til Tenant Access",
    roleTitle: "Hvem som har ansvaret",
    role: "Hvert selskap som registrerer seg bestemmer hvem som blir med og hvilke apper de kan åpne. Selskapet er behandlingsansvarlig for opplysningene om sine folk. Tenant Access lagrer og behandler opplysningene på vegne av selskapet.",
    storeTitle: "Hva vi lagrer",
    store: [
      ["Selskap", "Navn, e-postdomene, plan og logo hvis eieren laster opp en."],
      ["Personer", "Navn, jobb-e-post, konto-ID fra Google eller Microsoft, rolle, siste innlogging og om personen er slått av."],
      ["Apper", "Appene et selskap legger til, innloggingsinnstillingene deres og hvem som kan åpne hver av dem. Apphemmeligheter lagres som hash."],
      ["Revisjonslogg", "Hver innlogging og hvert innloggingsforsøk i apper: tidspunkt, resultat, IP-adresse og nettlesertype."],
      ["Betaling", "Kunde- og abonnements-ID fra Stripe. Kort- og Vipps-opplysninger blir hos Stripe."],
      ["Spør og agenter", "Bare hvis selskapet slår dem på: selskapets egen nøkkel til en AI-leverandør, lagret kryptert."],
    ],
    storeNote: "Vi ser og lagrer aldri passord. Det finnes ingen sporings- eller reklamekapsler. En innloggingskapsel holder deg innlogget og utløper etter 12 timer.",
    whereTitle: "Hvor det lagres",
    where: "Tjenesten kjører hos Render og databasen hos Neon, begge i Oregon, USA (AWS us-west-2). Trafikk til tenantaccess.me går gjennom Cloudflare. Det betyr at opplysningene i dag lagres utenfor EU og EØS.",
    whoTitle: "Hvem andre som behandler det",
    whoHead: ["Selskap", "Til hva", "Når"],
    who: [
      ["Render", "Kjører tjenesten", "Alltid"],
      ["Neon", "Drifter databasen", "Alltid"],
      ["Cloudflare", "DNS og nettverksbeskyttelse", "Alltid"],
      ["Google, Microsoft", "Bekrefter hvem du er ved innlogging", "Når du logger inn med dem"],
      ["Stripe", "Kort- og Vipps-betaling", "Bare betalende selskaper"],
      ["OpenAI, Anthropic eller Google", "Svarer på spørsmål i Spør og agenter, med de selskapsopplysningene spørsmålet trenger", "Bare hvis selskapet legger inn sin egen nøkkel"],
    ],
    keepTitle: "Hvor lenge vi lagrer det",
    keep: "Personer, apper og revisjonshendelser blir liggende til de fjernes. Planen bestemmer hvor langt tilbake revisjonsloggen viser (14, 90 eller 365 dager), men eldre hendelser slettes ikke. Når en person slås av, stoppes all innlogging med en gang, og oppføringen blir liggende slik at revisjonsloggen fortsatt gir mening.",
    rightsTitle: "Se, rette eller slette opplysningene dine",
    rights: "Spør eieren av selskapet ditt først. Eiere kan endre rollen din eller slå deg av under Personer. Å slette en person eller et helt selskap er ikke selvbetjent ennå, så eieren må be den som drifter Tenant Access om det.",
  },
};

export default function PrivacyPage() {
  const { lang } = useLang();
  const c = COPY[lang];

  return (
    <main className="legal">
      <header className="legal-top">
        <a className="brand legal-brand" href="/">
          <BrandMark size={28} />
          <span className="brand-name">Tenant Access</span>
        </a>
        <LanguageToggle />
      </header>

      <article className="legal-body" lang={lang === "no" ? "nb" : "en"}>
        <h1>{c.title}</h1>
        <p className="legal-lead">{c.lead}</p>
        <p className="hint">{c.updated}</p>

        <h2>{c.roleTitle}</h2>
        <p>{c.role}</p>

        <h2>{c.storeTitle}</h2>
        <dl className="legal-list">
          {c.store.map(([term, body]) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{body}</dd>
            </div>
          ))}
        </dl>
        <p>{c.storeNote}</p>

        <h2>{c.whereTitle}</h2>
        <p>{c.where}</p>

        <h2>{c.whoTitle}</h2>
        <div className="table-wrap">
          <table className="table legal-table">
            <thead>
              <tr>
                {c.whoHead.map((h) => (
                  <th key={h} scope="col">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.who.map(([name, what, when]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{what}</td>
                  <td>{when}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h2>{c.keepTitle}</h2>
        <p>{c.keep}</p>

        <h2>{c.rightsTitle}</h2>
        <p>{c.rights}</p>

        <p className="legal-back">
          <a href="/">{c.back}</a>
        </p>
      </article>
    </main>
  );
}
