import BrandMark from "./BrandMark";
import { Lang, useLang } from "./i18n";
import LanguageToggle from "./LanguageToggle";
import { pagePath } from "./routes";

type Row = [string, string];

type Copy = {
  title: string;
  updated: string;
  lead: string;
  back: string;
  operatorTitle: string;
  operator: string;
  roleTitle: string;
  role: string;
  dpaLink: string;
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
  contactTitle: string;
  contact: string;
};

/*
 * Keep this page true to the running service. If the hosting region, a
 * subprocessor or what the database stores changes, change it here in both
 * languages in the same pull request.
 */
export const PRIVACY_COPY: Record<Lang, Copy> = {
  en: {
    title: "Privacy and hosting",
    updated: "Last updated 28 November 2026.",
    lead: "What Tenant Access stores, where it is stored, and who else handles it.",
    back: "Back to Tenant Access",
    operatorTitle: "Who runs Tenant Access",
    operator: "Tenant Access is run by Teknologihjelpen, a sole proprietorship registered in Norway (org. no. 829 416 042). Contact: post@teknologihjelpen.no.",
    roleTitle: "Who is responsible",
    dpaLink: "Read the data processing agreement",
    role: "Each company that registers decides who joins and which apps they may open. The company is the controller for its people's data. Tenant Access is the processor: it stores and processes that data on the company's behalf and only for running the service. For visits to this website and for billing, Teknologihjelpen is the controller.",
    storeTitle: "What we store",
    store: [
      ["Company", "Name, email domain, plan, and a logo if the owner uploads one."],
      ["People", "Name, work email, the account ID from Google or Microsoft, role, last sign-in, and whether the person is switched off. For outside admins, also which companies they belong to and the invites sent to their address."],
      ["Apps", "The apps a company adds, their sign-in settings, and who may open each one. App secrets are stored hashed."],
      ["Audit log", "Every sign-in and app sign-in attempt: time, result, IP address and browser type."],
      ["Billing", "Stripe customer and subscription IDs. Card and Vipps details stay with Stripe."],
      ["Ask and agents", "How many questions a company asked Ask today. Questions and answers are not stored. If a company adds its own AI provider key for Ask or agents, the key is stored encrypted."],
      ["Webhooks", "Only if a company adds one: the address it gave and a signing secret, stored encrypted. Audit events are sent to that address, and the delivery records are kept for 30 days."],
    ],
    storeNote: "We never see or store passwords. There are no tracking or advertising cookies. One sign-in cookie keeps you signed in and expires after 12 hours. We count visits with Cloudflare Web Analytics, which uses no cookies and stores nothing on your device. It sees the page, the site you came from, your country and browser type, and does not identify you or follow you to other sites. Fonts are served from tenantaccess.me, not Google.",
    whereTitle: "Where it is stored",
    where: "The service runs on Render and the database on Neon, both in Oregon, USA (AWS us-west-2). Traffic to tenantaccess.me passes through Cloudflare. This means data is stored outside the EU and EEA today. These transfers rely on each provider's data processing agreement, which includes the EU standard contractual clauses.",
    whoTitle: "Who else handles it",
    whoHead: ["Company", "What for", "When"],
    who: [
      ["Render", "Runs the service", "Always"],
      ["Neon", "Hosts the database", "Always"],
      ["Cloudflare", "DNS, network protection and cookieless visit counts", "Always"],
      ["Cloudflare Workers AI", "Answers questions in Ask with the built-in model. The question is sent with the workspace details it needs, which can include people's names, emails, roles and recent sign-in events, but never IP addresses or app secrets. Cloudflare does not keep the question or answer and does not use them to train models.", "When someone uses Ask, unless the owner has turned it off or the company uses its own key"],
      ["Google, Microsoft", "Confirms who you are at sign-in", "When you sign in with them"],
      ["Stripe", "Card and Vipps payments", "Paying companies only"],
      ["OpenAI, Anthropic or Google", "Answers questions in agents, and in Ask if the company uses its own Gemini key. The question is sent with the same workspace details as above. The company's own agreement with the provider applies.", "Only if the company adds its own key"],
    ],
    keepTitle: "How long we keep it",
    keep: "People, apps and audit events stay until the owner deletes them. Your plan decides how far back the audit log shows (14, 90 or 365 days), but older events are not deleted. Switching a person off stops every sign-in at once, and the record stays so the audit log still makes sense.",
    rightsTitle: "Seeing, correcting or deleting your data",
    rights: "Ask the owner of your company first. Owners can change your role, switch you off or delete you under People, and can delete the whole company under Organization. Deleting a person removes their account and app access, and removes their name, email and IP address from the audit log; the events themselves stay. Deleting a company removes everything stored for it at once. Stripe keeps its own payment records for accounting.",
    contactTitle: "Questions and complaints",
    contact: "Write to post@teknologihjelpen.no about anything on this page. If you think your data is handled wrongly, you can also complain to the Norwegian Data Protection Authority (Datatilsynet) at datatilsynet.no.",
  },
  no: {
    title: "Personvern og drift",
    updated: "Sist oppdatert 28. november 2026.",
    lead: "Hva Tenant Access lagrer, hvor det lagres, og hvem andre som behandler det.",
    back: "Tilbake til Tenant Access",
    operatorTitle: "Hvem som driver Tenant Access",
    operator: "Tenant Access drives av Teknologihjelpen, et enkeltpersonforetak registrert i Norge (org.nr. 829 416 042). Kontakt: post@teknologihjelpen.no.",
    roleTitle: "Hvem som har ansvaret",
    dpaLink: "Les databehandleravtalen",
    role: "Hvert selskap som registrerer seg bestemmer hvem som blir med og hvilke apper de kan åpne. Selskapet er behandlingsansvarlig for opplysningene om sine folk. Tenant Access er databehandler: vi lagrer og behandler opplysningene på vegne av selskapet og bare for å drive tjenesten. For besøk på dette nettstedet og for fakturering er Teknologihjelpen behandlingsansvarlig.",
    storeTitle: "Hva vi lagrer",
    store: [
      ["Selskap", "Navn, e-postdomene, plan og logo hvis eieren laster opp en."],
      ["Personer", "Navn, jobb-e-post, konto-ID fra Google eller Microsoft, rolle, siste innlogging og om personen er slått av. For eksterne administratorer også hvilke selskaper de er med i og invitasjonene som er sendt til adressen deres."],
      ["Apper", "Appene et selskap legger til, innloggingsinnstillingene deres og hvem som kan åpne hver av dem. Apphemmeligheter lagres som hash."],
      ["Revisjonslogg", "Hver innlogging og hvert innloggingsforsøk i apper: tidspunkt, resultat, IP-adresse og nettlesertype."],
      ["Betaling", "Kunde- og abonnements-ID fra Stripe. Kort- og Vipps-opplysninger blir hos Stripe."],
      ["Spør og agenter", "Hvor mange spørsmål et selskap har stilt i Spør i dag. Spørsmål og svar lagres ikke. Hvis selskapet legger inn sin egen nøkkel til en AI-leverandør for Spør eller agenter, lagres nøkkelen kryptert."],
      ["Webhooks", "Bare hvis selskapet legger til en: adressen selskapet oppga og en signeringsnøkkel, lagret kryptert. Revisjonshendelser sendes til den adressen, og leveringsloggen lagres i 30 dager."],
    ],
    storeNote: "Vi ser og lagrer aldri passord. Det finnes ingen sporings- eller reklamekapsler. En innloggingskapsel holder deg innlogget og utløper etter 12 timer. Vi teller besøk med Cloudflare Web Analytics, som ikke bruker kapsler og ikke lagrer noe på enheten din. Den ser siden, nettstedet du kom fra, landet og nettlesertypen din, og identifiserer deg ikke eller følger deg til andre nettsteder. Skrifttypene leveres fra tenantaccess.me, ikke Google.",
    whereTitle: "Hvor det lagres",
    where: "Tjenesten kjører hos Render og databasen hos Neon, begge i Oregon, USA (AWS us-west-2). Trafikk til tenantaccess.me går gjennom Cloudflare. Det betyr at opplysningene i dag lagres utenfor EU og EØS. Overføringene bygger på databehandleravtalen med hver leverandør, som inneholder EUs standardavtaler (standard contractual clauses).",
    whoTitle: "Hvem andre som behandler det",
    whoHead: ["Selskap", "Til hva", "Når"],
    who: [
      ["Render", "Kjører tjenesten", "Alltid"],
      ["Neon", "Drifter databasen", "Alltid"],
      ["Cloudflare", "DNS, nettverksbeskyttelse og besøkstall uten kapsler", "Alltid"],
      ["Cloudflare Workers AI", "Svarer på spørsmål i Spør med den innebygde modellen. Spørsmålet sendes med de opplysningene om arbeidsområdet det trenger, som kan være navn, e-post, rolle og nylige innlogginger, men aldri IP-adresser eller apphemmeligheter. Cloudflare beholder ikke spørsmålet eller svaret og bruker dem ikke til å trene modeller.", "Når noen bruker Spør, med mindre eieren har slått det av eller selskapet bruker egen nøkkel"],
      ["Google, Microsoft", "Bekrefter hvem du er ved innlogging", "Når du logger inn med dem"],
      ["Stripe", "Kort- og Vipps-betaling", "Bare betalende selskaper"],
      ["OpenAI, Anthropic eller Google", "Svarer på spørsmål i agenter, og i Spør hvis selskapet bruker sin egen Gemini-nøkkel. Spørsmålet sendes med de samme opplysningene som over. Selskapets egen avtale med leverandøren gjelder.", "Bare hvis selskapet legger inn sin egen nøkkel"],
    ],
    keepTitle: "Hvor lenge vi lagrer det",
    keep: "Personer, apper og revisjonshendelser blir liggende til eieren sletter dem. Planen bestemmer hvor langt tilbake revisjonsloggen viser (14, 90 eller 365 dager), men eldre hendelser slettes ikke. Når en person slås av, stoppes all innlogging med en gang, og oppføringen blir liggende slik at revisjonsloggen fortsatt gir mening.",
    rightsTitle: "Se, rette eller slette opplysningene dine",
    rights: "Spør eieren av selskapet ditt først. Eiere kan endre rollen din, slå deg av eller slette deg under Personer, og kan slette hele selskapet under Organisasjon. Når en person slettes, fjernes kontoen og app-tilgangen, og navn, e-post og IP-adresse fjernes fra revisjonsloggen; selve hendelsene blir liggende. Når et selskap slettes, fjernes alt som er lagret for det med en gang. Stripe beholder sine egne betalingsopplysninger for regnskapet.",
    contactTitle: "Spørsmål og klager",
    contact: "Skriv til post@teknologihjelpen.no om alt på denne siden. Hvis du mener opplysningene dine behandles feil, kan du også klage til Datatilsynet på datatilsynet.no.",
  },
};

export default function PrivacyPage() {
  const { lang } = useLang();
  const c = PRIVACY_COPY[lang];

  return (
    <main className="legal">
      <header className="legal-top">
        <a className="brand legal-brand" href={pagePath("home", lang)}>
          <BrandMark size={28} />
          <span className="brand-name">Tenant Access</span>
        </a>
        <LanguageToggle />
      </header>

      <article className="legal-body" lang={lang === "no" ? "nb" : "en"}>
        <h1>{c.title}</h1>
        <p className="legal-lead">{c.lead}</p>
        <p className="hint">{c.updated}</p>

        <h2>{c.operatorTitle}</h2>
        <p>{c.operator}</p>

        <h2>{c.roleTitle}</h2>
        <p>{c.role}</p>
        <p>
          <a href={pagePath("dpa", lang)}>{c.dpaLink}</a>
        </p>

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

        <h2>{c.contactTitle}</h2>
        <p>{c.contact}</p>

        <p className="legal-back">
          <a href={pagePath("home", lang)}>{c.back}</a>
        </p>
      </article>
    </main>
  );
}
