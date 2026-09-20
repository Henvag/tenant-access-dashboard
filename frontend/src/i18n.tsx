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
  "feature.roles.body":
    "The first person on a domain becomes the company owner. Owners can promote admins.",

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
  "role.ownerLabel": "Owner",
  "role.ownerHint": "Company owner — registered this workspace",
  "role.adminHint": "Admin — promoted by the owner",
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
  "people.disable": "Disable",
  "people.enable": "Enable",
  "people.working": "Working…",
  "people.disableConfirm": "Disable access for {email}? They will not be able to sign in.",
  "people.promote": "Promote",
  "people.demote": "Demote",
  "people.demoteConfirm": "Demote {email} to member? They will lose admin access.",

  "audit.title": "Sign-in audit",
  "audit.hint": "{count} events · isolated to your tenant",
  "audit.event": "Event",
  "audit.idp": "Identity provider",
  "audit.detail": "Detail",
  "audit.reason": "Reason",
  "audit.details": "Details",
  "audit.code": "Code",
  "audit.time": "Time",
  "audit.expand": "Show details",
  "audit.collapse": "Hide details",
  "audit.ip": "IP",
  "audit.when": "When",
  "audit.login": "Sign-in",
  "audit.loginDetail": "Signed in successfully",
  "reason.no_tenant": "No company",
  "reason.invalid_domain": "Invalid domain",
  "reason.domain_mismatch": "Domain mismatch",
  "reason.missing_claims": "Missing email",
  "reason.unverified_email": "Unverified email",
  "reason.identity_conflict": "Identity conflict",
  "reason.user_disabled": "Account disabled",
  "reason.oidc_failed": "Provider error",
  "reason.unknown": "Unknown",
  "reason.byAdmin": "By admin",
  "reason.byOwner": "By owner",
  "reason.toAdmin": "→ Admin",
  "reason.toMember": "→ Member",
  "people.actions": "Actions",
  "people.moreActions": "More actions",
  "audit.loginFailed": "Failed sign-in",
  "audit.userDisabled": "Access disabled",
  "audit.userEnabled": "Access enabled",
  "audit.userDisabledDetail": "An admin disabled this account",
  "audit.userEnabledDetail": "An admin re-enabled this account",
  "audit.roleChanged": "Role changed",
  "audit.roleChangedDetail": "Role updated by the owner",
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
  "table.access": "Access",
  "table.you": "You",
  "status.disabled": "Disabled",
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
  "error.user_not_found": "That person was not found.",
  "error.cannot_disable_self": "You cannot disable your own account.",
  "error.cannot_disable_last_admin": "You cannot disable the last active admin.",
  "error.user_disabled": "This account has been disabled.",
  "error.cannot_disable_owner": "You cannot disable the company owner.",
  "error.cannot_disable_admin": "Only the owner can disable another admin.",
  "error.owner_required": "Only the company owner can change roles.",
  "error.cannot_change_own_role": "You cannot change your own role.",
  "error.cannot_change_owner_role": "The company owner's role cannot be changed.",
  "error.cannot_demote_last_admin": "You cannot demote the last active admin.",

  "auth.no_tenant":
    "No company is registered for your email domain yet. Register it first, then sign in.",
  "auth.invalid_domain": "That email domain is not valid.",
  "auth.domain_mismatch": "Your Google account domain does not match this Workspace.",
  "auth.missing_claims": "Sign-in did not return a verified email. Try again.",
  "auth.unverified_email": "Your email is not verified.",
  "auth.identity_conflict": "This email is already linked to a different identity.",
  "auth.user_disabled": "Your account has been disabled by an admin.",
  "auth.oidc_failed": "Sign-in failed. Try again.",
  "auth.generic": "Sign-in error: {code}",
  "auth.app_unknown_client": "That app is not registered here.",
  "auth.app_invalid_redirect":
    "The app sent an unregistered redirect address, so sign-in was stopped for safety.",
  "auth.app_access_denied": "You don't have access to {app}.",
  "denied.not_assigned": "An admin hasn't assigned it to you yet.",
  "denied.admins_only": "Only admins can use this app.",
  "denied.user_disabled": "Your account is disabled.",
  "denied.wrong_tenant": "It belongs to a different company.",
  "denied.app_disabled": "The app has been disabled by an admin.",
  "landing.continue": "Sign in to continue to {app}",
  "feature.apps.title": "One login for your other apps",
  "feature.apps.body":
    "Register Grafana or any OpenID Connect app and your team signs in to it with the same account.",

  "nav.apps": "Apps",
  "apps.title": "Apps",
  "apps.hint": "Apps that sign in through {tenant}. This dashboard is their identity provider.",
  "apps.new": "New app",
  "apps.newTitle": "Register an app",
  "apps.newHint": "Anything that speaks OpenID Connect can sign in through {tenant}.",
  "apps.emptyTitle": "No apps yet",
  "apps.emptyBody":
    "Register an app that supports OpenID Connect — Grafana, Outline, your own service — and people sign in to it with their work account.",
  "apps.issuer": "Issuer",
  "apps.issuerHint":
    "Paste this into the app's OpenID Connect settings. It publishes discovery, JWKS and the endpoints below.",
  "apps.endpoints": "Endpoints",
  "apps.clientId": "Client ID",
  "apps.clientSecret": "Client secret",
  "apps.secretOnce": "Copy it now — it is shown only once. You can rotate it later.",
  "apps.created": "{name} is registered",
  "apps.rotated": "New secret for {name}",
  "apps.nameLabel": "Name",
  "apps.redirects": "Redirect URIs",
  "apps.redirectsHint": "One per line. The app's callback address; must match exactly.",
  "apps.launchUrl": "Launch URL",
  "apps.launchUrlHint": "Where the tile on Overview sends people. Optional.",
  "apps.policy": "Who can sign in",
  "policy.everyone": "Everyone",
  "policy.admins": "Admins only",
  "policy.assigned": "Assigned people",
  "policy.everyoneHint": "Every active person in {tenant}.",
  "policy.adminsHint": "The owner and promoted admins.",
  "policy.assignedHint": "Only people you pick under Manage access.",
  "apps.create": "Create app",
  "apps.creating": "Creating…",
  "apps.save": "Save",
  "apps.saving": "Saving…",
  "apps.cancel": "Cancel",
  "apps.done": "Done",
  "apps.copy": "Copy",
  "apps.copied": "Copied",
  "apps.manageAccess": "Manage access",
  "apps.edit": "Edit",
  "apps.rotate": "Rotate secret",
  "apps.rotateConfirm":
    "Rotate the secret for {name}? The app stops signing people in until you paste the new one.",
  "apps.disable": "Disable",
  "apps.enable": "Enable",
  "apps.delete": "Delete",
  "apps.deleteConfirm": "Delete {name}? Sign-ins to it stop immediately.",
  "apps.grants": "{count} assigned",
  "apps.accessTitle": "Access to {name}",
  "apps.accessHint": "Pick who may sign in. Every change is written to the audit log.",
  "apps.settingsFor": "Settings for {name}",
  "apps.open": "Open",
  "apps.moreActions": "More actions",
  "apps.grafanaTip": "Grafana: set the redirect URI to {url}/login/generic_oauth.",
  "apps.outlineTip": "Outline: set the redirect URI to {url}/auth/oidc.callback.",
  "apps.redirectTip": "Register the app's callback URL under Redirect URIs (see its OIDC docs).",

  "myapps.title": "Your apps",
  "myapps.hint": "One click — this dashboard vouches for you.",
  "myapps.empty": "No apps have been shared with you yet.",
  "myapps.noLaunch": "No launch URL set",

  "audit.appLogin": "App sign-in",
  "audit.appLoginDenied": "App access denied",
  "audit.appCreated": "App registered",
  "audit.appDeleted": "App deleted",
  "audit.appGranted": "App access granted",
  "audit.appRevoked": "App access revoked",
  "audit.appLoginDetail": "Signed in to {app} through this dashboard",
  "audit.appLoginDeniedDetail": "Tried to sign in to {app} and was refused",
  "audit.appCreatedDetail": "Registered {app} as an OpenID Connect app",
  "audit.appDeletedDetail": "Deleted the app {app}",
  "audit.appGrantedDetail": "Given access to {app} by {by}",
  "audit.appRevokedDetail": "Access to {app} removed by {by}",
  "reason.not_assigned": "Not assigned",
  "reason.admins_only": "Admins only",
  "reason.wrong_tenant": "Other company",
  "reason.app_disabled": "App disabled",
  "error.app_not_found": "That app no longer exists.",
  "error.app_limit_reached": "You can register up to 25 apps.",
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
  "feature.roles.body":
    "Den første på et domene blir selskapseier. Eiere kan forfremme administratorer.",

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
  "role.ownerLabel": "Eier",
  "role.ownerHint": "Selskapseier — registrerte denne arbeidsplassen",
  "role.adminHint": "Administrator — forfremmet av eieren",
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
  "people.disable": "Deaktiver",
  "people.enable": "Aktiver",
  "people.working": "Jobber…",
  "people.disableConfirm": "Deaktivere tilgang for {email}? De vil ikke kunne logge inn.",
  "people.promote": "Forfrem",
  "people.demote": "Nedgrader",
  "people.demoteConfirm": "Nedgradere {email} til medlem? De mister administratortilgang.",

  "audit.title": "Innloggingsrevisjon",
  "audit.hint": "{count} hendelser · isolert til din tenant",
  "audit.event": "Hendelse",
  "audit.idp": "Identitetsleverandør",
  "audit.detail": "Detalj",
  "audit.reason": "Årsak",
  "audit.details": "Detaljer",
  "audit.code": "Kode",
  "audit.time": "Tidspunkt",
  "audit.expand": "Vis detaljer",
  "audit.collapse": "Skjul detaljer",
  "audit.ip": "IP",
  "audit.when": "Når",
  "audit.login": "Innlogging",
  "audit.loginDetail": "Logget inn",
  "reason.no_tenant": "Ingen selskap",
  "reason.invalid_domain": "Ugyldig domene",
  "reason.domain_mismatch": "Feil domene",
  "reason.missing_claims": "Mangler e-post",
  "reason.unverified_email": "Uverifisert e-post",
  "reason.identity_conflict": "Identitetskonflikt",
  "reason.user_disabled": "Konto deaktivert",
  "reason.oidc_failed": "Leverandørfeil",
  "reason.unknown": "Ukjent",
  "reason.byAdmin": "Av administrator",
  "reason.byOwner": "Av eier",
  "reason.toAdmin": "→ Administrator",
  "reason.toMember": "→ Medlem",
  "people.actions": "Handlinger",
  "people.moreActions": "Flere handlinger",
  "audit.loginFailed": "Mislykket innlogging",
  "audit.userDisabled": "Tilgang deaktivert",
  "audit.userEnabled": "Tilgang aktivert",
  "audit.userDisabledDetail": "En administrator deaktiverte denne kontoen",
  "audit.userEnabledDetail": "En administrator aktiverte denne kontoen på nytt",
  "audit.roleChanged": "Rolle endret",
  "audit.roleChangedDetail": "Rollen ble oppdatert av eieren",
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
  "table.access": "Tilgang",
  "table.you": "Deg",
  "status.disabled": "Deaktivert",
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
  "error.user_not_found": "Fant ikke den personen.",
  "error.cannot_disable_self": "Du kan ikke deaktivere din egen konto.",
  "error.cannot_disable_last_admin": "Du kan ikke deaktivere den siste aktive administratoren.",
  "error.user_disabled": "Denne kontoen er deaktivert.",
  "error.cannot_disable_owner": "Du kan ikke deaktivere selskapseieren.",
  "error.cannot_disable_admin": "Bare eieren kan deaktivere en annen administrator.",
  "error.owner_required": "Bare selskapseieren kan endre roller.",
  "error.cannot_change_own_role": "Du kan ikke endre din egen rolle.",
  "error.cannot_change_owner_role": "Selskapseierens rolle kan ikke endres.",
  "error.cannot_demote_last_admin": "Du kan ikke nedgradere den siste aktive administratoren.",

  "auth.no_tenant":
    "Ingen selskap er registrert for e-postdomenet ditt enda. Registrer det først, og logg deretter inn.",
  "auth.invalid_domain": "E-postdomenet er ikke gyldig.",
  "auth.domain_mismatch": "Domenet på Google-kontoen stemmer ikke med denne Workspace-tenanten.",
  "auth.missing_claims": "Innlogging returnerte ikke en verifisert e-post. Prøv igjen.",
  "auth.unverified_email": "E-posten din er ikke verifisert.",
  "auth.identity_conflict": "Denne e-posten er allerede knyttet til en annen identitet.",
  "auth.user_disabled": "Kontoen din er deaktivert av en administrator.",
  "auth.oidc_failed": "Innlogging feilet. Prøv igjen.",
  "auth.generic": "Innloggingsfeil: {code}",
  "auth.app_unknown_client": "Den appen er ikke registrert her.",
  "auth.app_invalid_redirect":
    "Appen sendte en uregistrert omdirigeringsadresse, så innloggingen ble stoppet av sikkerhetshensyn.",
  "auth.app_access_denied": "Du har ikke tilgang til {app}.",
  "denied.not_assigned": "En administrator har ikke tildelt den til deg enda.",
  "denied.admins_only": "Bare administratorer kan bruke denne appen.",
  "denied.user_disabled": "Kontoen din er deaktivert.",
  "denied.wrong_tenant": "Den tilhører et annet selskap.",
  "denied.app_disabled": "Appen er deaktivert av en administrator.",
  "landing.continue": "Logg inn for å fortsette til {app}",
  "feature.apps.title": "Én innlogging for de andre appene dine",
  "feature.apps.body":
    "Registrer Grafana eller en annen OpenID Connect-app, og teamet logger inn med samme konto.",

  "nav.apps": "Apper",
  "apps.title": "Apper",
  "apps.hint": "Apper som logger inn via {tenant}. Dette dashbordet er identitetsleverandøren deres.",
  "apps.new": "Ny app",
  "apps.newTitle": "Registrer en app",
  "apps.newHint": "Alt som snakker OpenID Connect kan logge inn via {tenant}.",
  "apps.emptyTitle": "Ingen apper enda",
  "apps.emptyBody":
    "Registrer en app som støtter OpenID Connect – Grafana, Outline, din egen tjeneste – så logger folk inn med jobbkontoen sin.",
  "apps.issuer": "Utsteder",
  "apps.issuerHint":
    "Lim inn denne i appens OpenID Connect-innstillinger. Den publiserer discovery, JWKS og endepunktene under.",
  "apps.endpoints": "Endepunkter",
  "apps.clientId": "Klient-ID",
  "apps.clientSecret": "Klienthemmelighet",
  "apps.secretOnce": "Kopier den nå – den vises bare én gang. Du kan rotere den senere.",
  "apps.created": "{name} er registrert",
  "apps.rotated": "Ny hemmelighet for {name}",
  "apps.nameLabel": "Navn",
  "apps.redirects": "Omdirigerings-URIer",
  "apps.redirectsHint": "Én per linje. Appens callback-adresse; må stemme nøyaktig.",
  "apps.launchUrl": "Start-URL",
  "apps.launchUrlHint": "Hvor flisen på oversikten sender folk. Valgfritt.",
  "apps.policy": "Hvem kan logge inn",
  "policy.everyone": "Alle",
  "policy.admins": "Kun administratorer",
  "policy.assigned": "Tildelte personer",
  "policy.everyoneHint": "Alle aktive personer i {tenant}.",
  "policy.adminsHint": "Eieren og forfremmede administratorer.",
  "policy.assignedHint": "Bare personer du velger under Administrer tilgang.",
  "apps.create": "Opprett app",
  "apps.creating": "Oppretter…",
  "apps.save": "Lagre",
  "apps.saving": "Lagrer…",
  "apps.cancel": "Avbryt",
  "apps.done": "Ferdig",
  "apps.copy": "Kopier",
  "apps.copied": "Kopiert",
  "apps.manageAccess": "Administrer tilgang",
  "apps.edit": "Rediger",
  "apps.rotate": "Roter hemmelighet",
  "apps.rotateConfirm":
    "Rotere hemmeligheten for {name}? Appen slutter å logge folk inn til du limer inn den nye.",
  "apps.disable": "Deaktiver",
  "apps.enable": "Aktiver",
  "apps.delete": "Slett",
  "apps.deleteConfirm": "Slette {name}? Innlogginger til den stopper umiddelbart.",
  "apps.grants": "{count} tildelt",
  "apps.accessTitle": "Tilgang til {name}",
  "apps.accessHint": "Velg hvem som kan logge inn. Hver endring skrives til revisjonsloggen.",
  "apps.settingsFor": "Innstillinger for {name}",
  "apps.open": "Åpne",
  "apps.moreActions": "Flere handlinger",
  "apps.grafanaTip": "Grafana: sett omdirigerings-URI til {url}/login/generic_oauth.",
  "apps.outlineTip": "Outline: sett omdirigerings-URI til {url}/auth/oidc.callback.",
  "apps.redirectTip": "Registrer appens callback-URL under omdirigerings-URIer (se dens OIDC-dokumentasjon).",

  "myapps.title": "Dine apper",
  "myapps.hint": "Ett klikk – dette dashbordet går god for deg.",
  "myapps.empty": "Ingen apper er delt med deg enda.",
  "myapps.noLaunch": "Ingen start-URL satt",

  "audit.appLogin": "App-innlogging",
  "audit.appLoginDenied": "App-tilgang avvist",
  "audit.appCreated": "App registrert",
  "audit.appDeleted": "App slettet",
  "audit.appGranted": "App-tilgang gitt",
  "audit.appRevoked": "App-tilgang fjernet",
  "audit.appLoginDetail": "Logget inn i {app} via dette dashbordet",
  "audit.appLoginDeniedDetail": "Prøvde å logge inn i {app} og ble avvist",
  "audit.appCreatedDetail": "Registrerte {app} som en OpenID Connect-app",
  "audit.appDeletedDetail": "Slettet appen {app}",
  "audit.appGrantedDetail": "Fikk tilgang til {app} av {by}",
  "audit.appRevokedDetail": "Tilgang til {app} fjernet av {by}",
  "reason.not_assigned": "Ikke tildelt",
  "reason.admins_only": "Kun admin",
  "reason.wrong_tenant": "Annet selskap",
  "reason.app_disabled": "App deaktivert",
  "error.app_not_found": "Den appen finnes ikke lenger.",
  "error.app_limit_reached": "Du kan registrere opptil 25 apper.",
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
