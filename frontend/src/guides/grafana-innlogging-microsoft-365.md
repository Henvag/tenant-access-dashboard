Med Microsoft-innlogging slipper de ansatte et eget passord til Grafana. Når noen slutter, stenger dere én konto i stedet for to. Denne guiden viser oppsettet med Grafanas innebygde støtte for Microsoft Entra ID (det som før het Azure AD).

**Du trenger:**

- Administratortilgang til Microsoft Entra admin center (entra.microsoft.com).
- Administratortilgang til Grafana, og at Grafana er tilgjengelig på en fast adresse med HTTPS, for eksempel `https://grafana.firma.no`.

## 1. Registrer Grafana i Microsoft Entra

1. Gå til **Entra ID > App registrations > New registration**.
2. Gi appen et navn, for eksempel `Grafana`.
3. Velg **Accounts in this organizational directory only**, så bare deres egne ansatte kan logge inn.
4. Under **Redirect URI**, velg **Web** og skriv inn `https://grafana.firma.no/login/azuread`.
5. Klikk **Register**.
6. Kopier **Application (client) ID** og **Directory (tenant) ID** fra oversiktssiden. Du trenger begge senere.

## 2. Lag en klienthemmelighet

1. Gå til **Certificates & secrets > Client secrets > New client secret**.
2. Skriv en beskrivelse og velg hvor lenge den skal gjelde.
3. Kopier **Value** med en gang. Den vises bare én gang.

Skriv opp når hemmeligheten utløper. Når den går ut, slutter innloggingen å virke.

## 3. Lag roller for Viewer, Editor og Admin

Grafana kan lese rollen fra Microsoft, slik at dere styrer tilgangen ett sted.

1. Gå til **App roles > Create app role**.
2. Lag tre roller med typen **Users/Groups** og disse verdiene (Value): `Viewer`, `Editor` og `Admin`.
3. Gå til **Enterprise applications**, åpne `Grafana`, og velg **Users and groups**. Gi hver person eller gruppe én av rollene.

Under **Properties** i samme Enterprise application kan du slå på **Assignment required**. Da kan bare de du har lagt til, logge inn.

## 4. Sett opp Grafana

Du kan gjøre dette i Grafana under **Administration > Authentication** ved å velge Entra ID, eller i konfigurasjonsfilen `grafana.ini`:

```ini
[auth.azuread]
name = Microsoft 365
enabled = true
allow_sign_up = true
client_id = APPLICATION_CLIENT_ID
client_secret = CLIENT_SECRET
scopes = openid email profile
auth_url = https://login.microsoftonline.com/TENANT_ID/oauth2/v2.0/authorize
token_url = https://login.microsoftonline.com/TENANT_ID/oauth2/v2.0/token
allowed_organizations = TENANT_ID
role_attribute_strict = true
use_pkce = true
```

Bytt ut `APPLICATION_CLIENT_ID`, `CLIENT_SECRET` og `TENANT_ID` med verdiene fra steg 1 og 2.

Kjører du Grafana i Docker, kan du bruke miljøvariabler i stedet. Navnet bygges av seksjonen og nøkkelen, for eksempel `GF_AUTH_AZUREAD_CLIENT_ID` og `GF_AUTH_AZUREAD_CLIENT_SECRET`.

Hva innstillingene gjør:

- `allowed_organizations` sørger for at bare kontoer fra deres egen Microsoft-organisasjon slipper inn.
- `role_attribute_strict = true` stopper personer som ikke har fått noen rolle i steg 3, i stedet for å gi dem Viewer automatisk.
- `use_pkce = true` gjør innloggingen sikrere og er anbefalt av Grafana.

Start Grafana på nytt etter endringen.

## 5. Test innloggingen

1. Åpne Grafana i et privat nettleservindu.
2. Klikk **Sign in with Microsoft 365**.
3. Logg inn med en vanlig ansattkonto, og sjekk at personen får riktig rolle under **Administration > Users**.

Når alt virker, kan du skjule det vanlige innloggingsskjemaet med `disable_login_form = true` under `[auth]`. Behold en lokal administratorkonto i tilfelle Microsoft-innloggingen slutter å virke.

## Vanlige feil

- **"Redirect URI mismatch"**: Adressen i steg 1 må være helt lik Grafanas adresse, med `https` og uten skråstrek til slutt. Sjekk også at `root_url` under `[server]` i Grafana er riktig.
- **Brukeren slipper ikke inn**: Personen har ikke fått en rolle i steg 3, eller **Assignment required** er slått på uten at personen er lagt til.
- **Innloggingen sluttet plutselig å virke**: Klienthemmeligheten har sannsynligvis utløpt. Lag en ny i steg 2 og oppdater Grafana.

## Når noen slutter

Blokkerer du kontoen i Microsoft, kommer personen ikke inn i Grafana igjen. Men en økt som allerede er åpen, kan vare en stund. Deaktiver derfor brukeren i Grafana også, under **Administration > Users**. Se også [sjekklisten for når en ansatt slutter](/no/guider/stenge-tilgang-ansatt-slutter).

---

Har dere flere verktøy enn Grafana, må dette oppsettet gjøres én gang for hvert av dem. Tenant Access lar dere koble til verktøyene ett sted og styre hvem som har tilgang til hva. [Les mer om Tenant Access](/no).
