export type StudentNavigationItem = {
  href: string;
  label: "学习" | "实训" | "成长" | "我的";
};

export const STUDENT_NAVIGATION: readonly StudentNavigationItem[] = [
  { href: "/home", label: "学习" },
  { href: "/annotation", label: "实训" },
  { href: "/progress", label: "成长" },
  { href: "/settings", label: "我的" },
] as const;

const STUDENT_ALLOWED_ROUTES = [
  "/home",
  "/annotation",
  "/progress",
  "/settings",
  "/settings/appearance",
] as const;

function matchesRoute(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(`${route}/`);
}

/**
 * Student accounts use an explicit allow-list. This is intentionally stricter
 * than hiding links: direct navigation to infrastructure pages is redirected
 * before the page is rendered. The backend remains the final authority for
 * every API call.
 */
export function isStudentRouteAllowed(pathname: string): boolean {
  if (pathname === "/settings") return true;
  if (pathname.startsWith("/settings/")) {
    return matchesRoute(pathname, "/settings/appearance");
  }
  return STUDENT_ALLOWED_ROUTES.some((route) => matchesRoute(pathname, route));
}

