import { TKey } from "./i18n";

export type AppTemplateId =
  | "grafana"
  | "outline"
  | "portainer"
  | "gitea"
  | "bookstack"
  | "slack"
  | "custom"
  | "saml";

export type AppTemplate = {
  id: AppTemplateId;
  /** Default display name when creating (empty for custom). */
  defaultName: string;
  /** Mark matching for AppMark logos. */
  markName: string;
  titleKey: TKey;
  bodyKey: TKey;
  pathHintKey: TKey;
  /** Path appended to base URL for redirect URI; null = manual entry. */
  redirectPath: string | null;
  /** Path appended to base URL for launch URL; null = use base or manual. */
  launchPath: string | null;
  /** Tip key used after create (needs {url} = origin). */
  tipKey: TKey;
  /**
   * People don't sign in through us; we only create and deactivate their account
   * in the app. No redirect URIs, no client secret to hand over.
   */
  accountsOnly?: { launchUrl: string };
  /**
   * Signs in with SAML. With an acsPath, the admin enters the app's base URL
   * (e.g. their Slack workspace) and we derive the rest; without, they type
   * the entity ID and ACS URL.
   */
  saml?: { entityId: string | null; acsPath: string | null; nameid: "email" | "persistent" };
};

export const APP_CATALOG: AppTemplate[] = [
  {
    id: "grafana",
    defaultName: "Grafana",
    markName: "Grafana",
    titleKey: "catalog.grafana.title",
    bodyKey: "catalog.grafana.body",
    pathHintKey: "catalog.grafana.path",
    redirectPath: "/login/generic_oauth",
    launchPath: "/login/generic_oauth",
    tipKey: "apps.grafanaTip",
  },
  {
    id: "outline",
    defaultName: "Outline",
    markName: "Outline",
    titleKey: "catalog.outline.title",
    bodyKey: "catalog.outline.body",
    pathHintKey: "catalog.outline.path",
    redirectPath: "/auth/oidc.callback",
    launchPath: "/",
    tipKey: "apps.outlineTip",
  },
  {
    id: "portainer",
    defaultName: "Portainer",
    markName: "Portainer",
    titleKey: "catalog.portainer.title",
    bodyKey: "catalog.portainer.body",
    pathHintKey: "catalog.portainer.path",
    redirectPath: "/",
    launchPath: "/",
    tipKey: "apps.portainerTip",
  },
  {
    id: "gitea",
    defaultName: "Gitea",
    markName: "Gitea",
    titleKey: "catalog.gitea.title",
    bodyKey: "catalog.gitea.body",
    pathHintKey: "catalog.gitea.path",
    redirectPath: "/user/oauth2/tenant-access/callback",
    launchPath: "/",
    tipKey: "apps.giteaTip",
  },
  {
    id: "bookstack",
    defaultName: "BookStack",
    markName: "BookStack",
    titleKey: "catalog.bookstack.title",
    bodyKey: "catalog.bookstack.body",
    pathHintKey: "catalog.bookstack.path",
    redirectPath: "/oidc/callback",
    launchPath: "/",
    tipKey: "apps.bookstackTip",
  },
  {
    id: "slack",
    defaultName: "Slack",
    markName: "Slack",
    titleKey: "catalog.slack.title",
    bodyKey: "catalog.slack.body",
    pathHintKey: "catalog.slack.path",
    redirectPath: null,
    launchPath: null,
    tipKey: "apps.redirectTip",
    // Slack wants a NameID that never changes, even if the email does.
    saml: { entityId: "https://slack.com", acsPath: "/sso/saml", nameid: "persistent" },
  },
  {
    id: "custom",
    defaultName: "",
    markName: "OpenID Connect",
    titleKey: "catalog.custom.title",
    bodyKey: "catalog.custom.body",
    pathHintKey: "catalog.custom.path",
    redirectPath: null,
    launchPath: null,
    tipKey: "apps.redirectTip",
  },
  {
    id: "saml",
    defaultName: "",
    markName: "SAML",
    titleKey: "catalog.saml.title",
    bodyKey: "catalog.saml.body",
    pathHintKey: "catalog.saml.path",
    redirectPath: null,
    launchPath: null,
    tipKey: "apps.redirectTip",
    saml: { entityId: null, acsPath: null, nameid: "email" },
  },
];

export function templateById(id: AppTemplateId): AppTemplate {
  return APP_CATALOG.find((t) => t.id === id) ?? APP_CATALOG[APP_CATALOG.length - 1];
}

/** Strip trailing slash from a base URL. */
export function normalizeBaseUrl(raw: string): string {
  return raw.trim().replace(/\/+$/, "");
}

export function urlsFromTemplate(
  template: AppTemplate,
  baseUrl: string,
): { redirect: string; launch: string } {
  const base = normalizeBaseUrl(baseUrl);
  if (!base || !template.redirectPath) {
    return { redirect: "", launch: "" };
  }
  // "/" means the app root (often with a trailing slash for OAuth callbacks).
  const redirect =
    template.redirectPath === "/" ? `${base}/` : `${base}${template.redirectPath}`;
  const launch =
    template.launchPath === "/" || !template.launchPath
      ? base
      : `${base}${template.launchPath}`;
  return { redirect, launch };
}
