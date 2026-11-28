Når noen slutter, er det lett å stenge Microsoft 365-kontoen og tro at alt er gjort. Men de fleste bedrifter har flere steder å logge inn: et overvåkingsverktøy, en wiki, et kodelager, et regnskapsprogram, en delt passordliste. Hvert av dem må stenges for seg.

Denne listen er laget for små bedrifter uten egen IT-avdeling. Gå gjennom den samme dag som arbeidsforholdet slutter.

## Før siste arbeidsdag

- **Lag en liste over alt personen har tilgang til.** Spør personen selv, og se gjennom fakturaer for programvare. Det er her de fleste glemmer noe.
- **Avtal hvem som overtar filer og e-post.** Bestem hvem som skal få dokumenter fra OneDrive og hvem kunder skal kontakte i stedet.
- **Flytt eierskap.** Delte mapper, Teams-kanaler, kalendere og kontoer som står i personens navn, bør få en ny eier før kontoen stenges.

## Siste arbeidsdag: Microsoft 365

Gjøres i Microsoft 365 admin center eller Microsoft Entra admin center.

1. **Blokker pålogging** for brukeren.
2. **Tilbakekall alle økter** (Revoke sessions). Blokkering alene logger ikke personen ut av apper som allerede er åpne på telefonen eller PC-en.
3. **Bytt passordet**, og fjern registrerte metoder for tofaktor, slik at kontoen ikke kan tas i bruk igjen ved et uhell.
4. **Sett opp et autosvar** som sier hvem man kan kontakte i stedet.
5. **Fjern lisensen** når filer og e-post er tatt vare på, så dere slutter å betale for den.

## Verktøy dere drifter selv

Her ligger den største risikoen. Verktøy som Grafana, Outline, Gitea eller Nextcloud har egne innloggingsøkter. Selv om de bruker Microsoft-innlogging, kan en økt som allerede er åpen fortsette å virke i timer eller dager etter at kontoen er blokkert i Microsoft.

For hvert verktøy:

- **Deaktiver eller slett brukeren** i verktøyet.
- **Logg brukeren ut av alle økter**, hvis verktøyet har en slik knapp.
- **Slett personlige tilgangsnøkler** (API-nøkler, tokens, SSH-nøkler). De virker uavhengig av passordet.

## Delte passord og nøkler

- **Bytt passord** personen kjente til, for eksempel delte kontoer, Wi-Fi og administratorpassord.
- **Fjern personen fra passordbehandleren**, og bytt passordene i hvelv personen hadde tilgang til.
- **Sjekk skytjenester og domener.** Står personen som eier eller administrator i for eksempel domeneregistraren, DNS eller en skyleverandør, må det flyttes.

## Utstyr og fysisk tilgang

- **Samle inn PC, telefon og eventuelle sikkerhetsnøkler.**
- **Tilbakestill eller fjern enhetene** fra Intune eller det dere bruker til å styre enheter.
- **Samle inn nøkler og adgangskort**, og stopp kortet i adgangssystemet.

## Etterpå: e-post og personopplysninger

Etter norsk regelverk skal en tidligere ansatts e-postkasse som hovedregel avsluttes når arbeidsforholdet slutter. Den kan holdes åpen i en kort periode bare hvis det er et særskilt behov, for eksempel et autosvar mens kunder får beskjed. Arbeidsgiver kan ikke fritt lese den gamle e-posten. Se [forskrift om arbeidsgivers innsyn i e-postkasse § 4](https://lovdata.no/forskrift/2018-07-02-1108) og [Datatilsynets veileder](https://www.datatilsynet.no/personvern-pa-ulike-omrader/personvern-pa-arbeidsplassen/innsyn-epost-filer/).

Skriv ned hva som ble stengt og når. Det gjør det lettere å svare hvis noen spør senere.

## Kort versjon

1. Blokker pålogging og tilbakekall økter i Microsoft 365.
2. Deaktiver brukeren og logg den ut i hvert verktøy dere drifter selv.
3. Slett personlige nøkler og bytt delte passord.
4. Samle inn utstyr, nøkler og kort.
5. Steng e-postkassen etter en kort overgang.

---

Tenant Access samler punkt 1 og 2 i én knapp: brukeren blir deaktivert og logget ut av de tilkoblede verktøyene på én gang, og alt blir loggført. [Les mer om Tenant Access](/no).
