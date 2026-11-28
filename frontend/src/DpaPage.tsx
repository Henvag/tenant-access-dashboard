import BrandMark from "./BrandMark";
import { Lang, useLang } from "./i18n";
import LanguageToggle from "./LanguageToggle";
import { pagePath } from "./routes";

type Block = string | { head: string[]; rows: string[][] } | { list: string[] };

type Section = { title: string; blocks: Block[] };

type Copy = {
  title: string;
  version: string;
  lead: string;
  back: string;
  privacyLink: string;
  sections: Section[];
};

/*
 * The data processing agreement (databehandleravtale) between Teknologihjelpen and each
 * customer company. Keep the subprocessor list in step with PrivacyPage.tsx, and keep
 * every promise here true to what the service does today. Change both languages in the
 * same pull request and bump the version date.
 */
export const DPA_COPY: Record<Lang, Copy> = {
  en: {
    title: "Data processing agreement",
    version: "Version of 28 November 2026.",
    lead: "The terms under which Tenant Access processes personal data for the companies that use it.",
    back: "Back to Tenant Access",
    privacyLink: "Privacy and hosting",
    sections: [
      {
        title: "1. Parties and acceptance",
        blocks: [
          "1.1 Controller: the company that registers on Tenant Access (\"the Customer\"). The Customer decides who may join and which apps they may open.",
          "1.2 Processor: Teknologihjelpen, org. no. 829 416 042, Norway, post@teknologihjelpen.no (\"Tenant Access\"), which runs the service at tenantaccess.me.",
          "1.3 The Customer accepts this agreement when it registers a company and uses the service. Tenant Access sends a signed copy on request.",
          "1.4 The agreement follows GDPR Article 28(3) and is modelled on the EU standard contractual clauses between controllers and processors (Commission Implementing Decision (EU) 2021/915).",
        ],
      },
      {
        title: "2. What is processed",
        blocks: [
          {
            head: ["", ""],
            rows: [
              ["Purpose", "Sign-in with Google or Microsoft to the Customer's dashboard and apps, access rules per app, an audit log, and billing."],
              ["Nature", "Storing, reading, matching sign-ins to accounts, issuing sign-in tokens to the Customer's apps, and deleting."],
              ["People", "The Customer's staff, outside admins the Customer invites (for example its IT firm), and people it invites by email."],
              ["Data", "Name, work email, account ID from Google or Microsoft, role, last sign-in, whether the person is switched off, which companies an outside admin belongs to, and invites sent to an address."],
              ["Audit log", "Time and result of each sign-in and app sign-in, IP address and browser type."],
              ["Optional", "Only if the Customer turns them on: its own AI provider key, stored encrypted, and its webhook addresses with their signing secrets, stored encrypted. Questions to Ask and agents are sent to the provider and not stored."],
              ["Sensitive data", "None is requested. The Customer should not put special category data (GDPR Article 9) into names or app names."],
              ["Duration", "As long as the Customer has a company on Tenant Access, then deletion as in 3.8."],
            ],
          },
          "Passwords are never received or stored.",
        ],
      },
      {
        title: "3. Duties of Tenant Access",
        blocks: [
          "3.1 Instructions. Tenant Access processes personal data only on the Customer's documented instructions: this agreement, the settings the Customer chooses in the dashboard, and written requests from its owner. Tenant Access tells the Customer at once if it believes an instruction breaks data protection law. If the law requires other processing, Tenant Access tells the Customer first, unless the law forbids that.",
          "3.2 Confidentiality. Only people who need access to run the service get it, and they are bound to confidentiality. Today that is the operator alone.",
          "3.3 Security. Tenant Access keeps the measures in section 6 and reviews them when the service changes.",
          "3.4 Subprocessors. The Customer gives general permission to use the subprocessors in section 4. Tenant Access gives at least 30 days' notice before adding or replacing one, by email to the owner and on this page. The Customer may object. If no solution is found, the Customer may end the agreement and delete its company. Each subprocessor is bound by a contract with the same data protection duties, and Tenant Access stays responsible for it.",
          "3.5 Rights of the people concerned. The dashboard lets the owner see everyone's data, change roles, switch people off, delete a person and export the audit log as CSV. If a person contacts Tenant Access directly, Tenant Access passes the request to the Customer without undue delay and does not answer for the Customer unless asked to.",
          "3.6 Other help. Tenant Access helps the Customer with security, impact assessments and prior consultation (GDPR Articles 32 to 36), using the information it has.",
          "3.7 Breaches. Tenant Access tells the owner without undue delay, and within 48 hours of becoming aware of a personal data breach. The notice says what happened, which data and people are affected, the likely consequences and what has been done. Facts not known yet follow as soon as they are.",
          "3.8 Deletion at the end. The owner can delete the company at any time under Organization, which removes all its data from the live database at once. Deleted data leaves the database's restore history within 7 days. The owner can export the audit log as CSV first. If the agreement ends without the owner deleting the company, Tenant Access deletes it within 90 days. Stripe keeps payment records under its own terms for accounting.",
          "3.9 Audits. Tenant Access gives the Customer the information needed to show it follows this agreement. The Customer, or an auditor it appoints, may audit with 30 days' notice, at its own cost and at most once a year, unless a breach or a supervisory authority calls for more.",
        ],
      },
      {
        title: "4. Subprocessors",
        blocks: [
          "The Customer approves these subprocessors. The list matches the privacy page and changes only as described in 3.4.",
          {
            head: ["Subprocessor", "What for", "Where"],
            rows: [
              ["Render", "Runs the service", "Oregon, USA"],
              ["Neon", "Hosts the database", "Oregon, USA (AWS us-west-2)"],
              ["Cloudflare", "DNS, network protection and cookieless visit counts for tenantaccess.me", "Global network"],
            ],
          },
          "These are not subprocessors of Tenant Access, because the Customer chooses them and uses them under its own account or terms:",
          {
            list: [
              "Google and Microsoft, which confirm who a person is at sign-in.",
              "Stripe, which takes card and Vipps payments under its own terms.",
              "OpenAI, Anthropic or Google AI, used only when the Customer adds its own key for Ask or agents.",
              "The Customer's own webhook endpoints, which receive audit events only if the Customer adds them.",
            ],
          },
        ],
      },
      {
        title: "5. Transfers outside the EEA",
        blocks: [
          "5.1 The service and its database run in the USA, so personal data is stored outside the EU and EEA.",
          "5.2 These transfers rely on the EU standard contractual clauses for transfers (Commission Implementing Decision (EU) 2021/914) in each subprocessor's data processing agreement, and, where a subprocessor is certified, on the EU-US Data Privacy Framework.",
          "5.3 Tenant Access does not move the data to another country without first giving notice under 3.4.",
        ],
      },
      {
        title: "6. Security measures",
        blocks: [
          {
            list: [
              "Separation between companies. Every request runs as one company. Postgres row-level security is forced on company tables, and the app's database role cannot bypass it. The app refuses to start in production if its role could.",
              "No passwords. People sign in with Google or Microsoft. Tenant Access never receives or stores a password.",
              "Secrets. Client secrets for the Customer's apps are stored hashed. AI provider keys and webhook secrets are stored encrypted.",
              "Sessions. One signed sign-in cookie, sent only over HTTPS, expires after 12 hours. Switching a person off ends their access at once, and apps with back-channel logout are told.",
              "Encryption in transit. All traffic to tenantaccess.me uses HTTPS through Cloudflare.",
              "Abuse limits. Sign-in endpoints are rate limited per IP address.",
              "Logging. Every sign-in, failed sign-in, app sign-in and admin change is written to the Customer's audit log, which its admins can read and export.",
              "Access to production. Limited to the operator.",
            ],
          },
        ],
      },
      {
        title: "7. Term, liability and law",
        blocks: [
          "7.1 This agreement runs as long as Tenant Access processes personal data for the Customer, and ends when the company is deleted under 3.8.",
          "7.2 Each party is liable for its own breaches of this agreement and of data protection law, as set out in GDPR Article 82.",
          "7.3 Tenant Access may update this agreement to follow the law or changes to the service, with 30 days' notice by email to the owner.",
          "7.4 Norwegian law applies, and disputes go to the Norwegian courts. If the English and Norwegian versions differ, the Norwegian one applies.",
        ],
      },
    ],
  },
  no: {
    title: "Databehandleravtale",
    version: "Versjon av 28. november 2026.",
    lead: "Vilkårene for hvordan Tenant Access behandler personopplysninger for selskapene som bruker tjenesten.",
    back: "Tilbake til Tenant Access",
    privacyLink: "Personvern og drift",
    sections: [
      {
        title: "1. Parter og aksept",
        blocks: [
          "1.1 Behandlingsansvarlig: selskapet som registrerer seg på Tenant Access («Kunden»). Kunden bestemmer hvem som kan bli med og hvilke apper de kan åpne.",
          "1.2 Databehandler: Teknologihjelpen, org.nr. 829 416 042, Norge, post@teknologihjelpen.no («Tenant Access»), som driver tjenesten på tenantaccess.me.",
          "1.3 Kunden godtar denne avtalen når den registrerer et selskap og bruker tjenesten. Tenant Access sender en signert kopi på forespørsel.",
          "1.4 Avtalen følger personvernforordningen artikkel 28 nr. 3 og bygger på EUs standardavtale mellom behandlingsansvarlige og databehandlere (kommisjonens gjennomføringsbeslutning (EU) 2021/915).",
        ],
      },
      {
        title: "2. Hva som behandles",
        blocks: [
          {
            head: ["", ""],
            rows: [
              ["Formål", "Innlogging med Google eller Microsoft til Kundens dashbord og apper, tilgangsregler per app, revisjonslogg og fakturering."],
              ["Art", "Lagring, lesing, kobling av innlogginger til kontoer, utstedelse av innloggingsbevis til Kundens apper, og sletting."],
              ["Personer", "Kundens ansatte, eksterne administratorer Kunden inviterer (for eksempel IT-leverandøren), og personer den inviterer på e-post."],
              ["Opplysninger", "Navn, jobb-e-post, konto-ID fra Google eller Microsoft, rolle, siste innlogging, om personen er slått av, hvilke selskaper en ekstern administrator er med i, og invitasjoner sendt til en adresse."],
              ["Revisjonslogg", "Tidspunkt og resultat for hver innlogging og app-innlogging, IP-adresse og nettlesertype."],
              ["Valgfritt", "Bare hvis Kunden slår det på: Kundens egen nøkkel til en AI-leverandør, lagret kryptert, og Kundens webhook-adresser med signeringsnøkler, lagret kryptert. Spørsmål til Spør og agenter sendes til leverandøren og lagres ikke."],
              ["Særlige kategorier", "Ingen etterspørres. Kunden bør ikke legge særlige kategorier av personopplysninger (artikkel 9) inn i navn eller appnavn."],
              ["Varighet", "Så lenge Kunden har et selskap på Tenant Access, deretter sletting som i punkt 3.8."],
            ],
          },
          "Passord mottas eller lagres aldri.",
        ],
      },
      {
        title: "3. Tenant Access sine plikter",
        blocks: [
          "3.1 Instrukser. Tenant Access behandler personopplysninger bare etter Kundens dokumenterte instrukser: denne avtalen, innstillingene Kunden velger i dashbordet, og skriftlige forespørsler fra eieren. Tenant Access sier fra med en gang hvis en instruks etter vår vurdering bryter personvernregelverket. Hvis loven krever annen behandling, sier Tenant Access fra til Kunden først, med mindre loven forbyr det.",
          "3.2 Taushetsplikt. Bare personer som trenger tilgang for å drive tjenesten får det, og de har taushetsplikt. I dag er det bare driftsansvarlig.",
          "3.3 Sikkerhet. Tenant Access opprettholder tiltakene i punkt 6 og går gjennom dem når tjenesten endres.",
          "3.4 Underleverandører. Kunden gir generell tillatelse til underleverandørene i punkt 4. Tenant Access varsler minst 30 dager før en underleverandør legges til eller byttes, på e-post til eieren og på denne siden. Kunden kan protestere. Finner vi ingen løsning, kan Kunden avslutte avtalen og slette selskapet. Hver underleverandør er bundet av en avtale med de samme personvernpliktene, og Tenant Access er fortsatt ansvarlig for den.",
          "3.5 De registrertes rettigheter. I dashbordet kan eieren se alles opplysninger, endre roller, slå av personer, slette en person og eksportere revisjonsloggen som CSV. Hvis en person kontakter Tenant Access direkte, sender Tenant Access forespørselen videre til Kunden uten ugrunnet opphold og svarer ikke på Kundens vegne med mindre Kunden ber om det.",
          "3.6 Annen bistand. Tenant Access hjelper Kunden med sikkerhet, konsekvensvurderinger og forhåndsdrøftinger (artikkel 32 til 36) ut fra opplysningene vi har.",
          "3.7 Avvik. Tenant Access varsler eieren uten ugrunnet opphold, og innen 48 timer etter at vi ble kjent med et brudd på personopplysningssikkerheten. Varselet sier hva som skjedde, hvilke opplysninger og personer som er berørt, sannsynlige konsekvenser og hva som er gjort. Det som ennå ikke er kjent, ettersendes så snart det er det.",
          "3.8 Sletting ved slutt. Eieren kan når som helst slette selskapet under Organisasjon, og da fjernes alle opplysningene fra databasen med en gang. Slettede opplysninger forsvinner fra databasens gjenopprettingshistorikk innen 7 dager. Eieren kan eksportere revisjonsloggen som CSV først. Hvis avtalen opphører uten at eieren har slettet selskapet, sletter Tenant Access det innen 90 dager. Stripe beholder betalingsopplysninger etter egne vilkår for regnskapet.",
          "3.9 Revisjon. Tenant Access gir Kunden opplysningene som trengs for å vise at avtalen følges. Kunden, eller en revisor Kunden utpeker, kan gjennomføre revisjon med 30 dagers varsel, for egen regning og høyst én gang i året, med mindre et avvik eller en tilsynsmyndighet krever mer.",
        ],
      },
      {
        title: "4. Underleverandører",
        blocks: [
          "Kunden godkjenner disse underleverandørene. Listen er den samme som på personvernsiden og endres bare som beskrevet i punkt 3.4.",
          {
            head: ["Underleverandør", "Til hva", "Hvor"],
            rows: [
              ["Render", "Kjører tjenesten", "Oregon, USA"],
              ["Neon", "Drifter databasen", "Oregon, USA (AWS us-west-2)"],
              ["Cloudflare", "DNS, nettverksbeskyttelse og besøkstall uten kapsler for tenantaccess.me", "Globalt nettverk"],
            ],
          },
          "Disse er ikke underleverandører for Tenant Access, fordi Kunden selv velger dem og bruker dem med egen konto eller egne vilkår:",
          {
            list: [
              "Google og Microsoft, som bekrefter hvem en person er ved innlogging.",
              "Stripe, som tar kort- og Vipps-betaling etter egne vilkår.",
              "OpenAI, Anthropic eller Google AI, bare når Kunden legger inn sin egen nøkkel til Spør eller agenter.",
              "Kundens egne webhook-adresser, som får revisjonshendelser bare hvis Kunden legger dem til.",
            ],
          },
        ],
      },
      {
        title: "5. Overføring ut av EØS",
        blocks: [
          "5.1 Tjenesten og databasen kjører i USA, så personopplysningene lagres utenfor EU og EØS.",
          "5.2 Overføringene bygger på EUs standardavtaler for overføring (kommisjonens gjennomføringsbeslutning (EU) 2021/914) i databehandleravtalen med hver underleverandør, og der underleverandøren er sertifisert, på EU–US Data Privacy Framework.",
          "5.3 Tenant Access flytter ikke opplysningene til et annet land uten å varsle først etter punkt 3.4.",
        ],
      },
      {
        title: "6. Sikkerhetstiltak",
        blocks: [
          {
            list: [
              "Skille mellom selskaper. Hver forespørsel kjører som ett selskap. Radnivåsikkerhet i Postgres er tvunget på for selskapstabellene, og appens databaserolle kan ikke omgå den. Appen nekter å starte i produksjon hvis rollen kunne det.",
              "Ingen passord. Folk logger inn med Google eller Microsoft. Tenant Access mottar eller lagrer aldri passord.",
              "Hemmeligheter. Klienthemmeligheter for Kundens apper lagres som hash. AI-nøkler og webhook-nøkler lagres kryptert.",
              "Økter. Én signert innloggingskapsel, sendt bare over HTTPS, som utløper etter 12 timer. Når en person slås av, stopper tilgangen med en gang, og apper med back-channel logout får beskjed.",
              "Kryptering under overføring. All trafikk til tenantaccess.me går over HTTPS gjennom Cloudflare.",
              "Begrensning av misbruk. Innloggingsendepunktene har grense for antall forsøk per IP-adresse.",
              "Logging. Hver innlogging, mislykket innlogging, app-innlogging og administratorendring skrives til Kundens revisjonslogg, som Kundens administratorer kan lese og eksportere.",
              "Tilgang til produksjon. Bare driftsansvarlig.",
            ],
          },
        ],
      },
      {
        title: "7. Varighet, ansvar og lovvalg",
        blocks: [
          "7.1 Avtalen gjelder så lenge Tenant Access behandler personopplysninger for Kunden, og opphører når selskapet slettes etter punkt 3.8.",
          "7.2 Hver part er ansvarlig for egne brudd på denne avtalen og på personvernregelverket, slik det følger av artikkel 82.",
          "7.3 Tenant Access kan oppdatere avtalen for å følge loven eller endringer i tjenesten, med 30 dagers varsel på e-post til eieren.",
          "7.4 Norsk rett gjelder, og tvister hører under norske domstoler. Hvis den engelske og den norske versjonen er ulike, gjelder den norske.",
        ],
      },
    ],
  },
};

function renderBlock(block: Block, key: number) {
  if (typeof block === "string") return <p key={key}>{block}</p>;
  if ("list" in block) {
    return (
      <ul key={key} className="legal-bullets">
        {block.list.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  }
  const hasHead = block.head.some(Boolean);
  return (
    <div key={key} className="table-wrap">
      <table className="table legal-table">
        {hasHead ? (
          <thead>
            <tr>
              {block.head.map((h) => (
                <th key={h} scope="col">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        ) : null}
        <tbody>
          {block.rows.map(([first, ...rest]) => (
            <tr key={first}>
              {hasHead ? <td>{first}</td> : <th scope="row">{first}</th>}
              {rest.map((cell) => (
                <td key={cell}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DpaPage() {
  const { lang } = useLang();
  const c = DPA_COPY[lang];

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
        <p className="hint">{c.version}</p>

        {c.sections.map((section) => (
          <section key={section.title}>
            <h2>{section.title}</h2>
            {section.blocks.map(renderBlock)}
          </section>
        ))}

        <p className="legal-back">
          <a href={pagePath("privacy", lang)}>{c.privacyLink}</a>
          {" · "}
          <a href={pagePath("home", lang)}>{c.back}</a>
        </p>
      </article>
    </main>
  );
}
