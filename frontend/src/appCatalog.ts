import { TKey } from "./i18n";

export type AppTemplateId =
  | "grafana"
  | "outline"
  | "portainer"
  | "gitea"
  | "bookstack"
  | "custom";

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
    id: "custom",
    defaultName: "",
    markName: "Custom",
    titleKey: "catalog.custom.title",
    bodyKey: "catalog.custom.body",
    pathHintKey: "catalog.custom.path",
    redirectPath: null,
    launchPath: null,
    tipKey: "apps.redirectTip",
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
