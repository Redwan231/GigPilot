import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/", "/login", "/signup"];
const AUTH_ONLY = ["/login", "/signup"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  // Check for refresh token cookie as a proxy for "has a session"
  const hasSession = req.cookies.has("refresh_token");

  const isProtected = !PUBLIC_PATHS.some((p) => pathname === p) && !pathname.startsWith("/_next");
  const isAuthPage = AUTH_ONLY.includes(pathname);

  if (isProtected && !hasSession) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthPage && hasSession) {
    const appUrl = req.nextUrl.clone();
    appUrl.pathname = "/app";
    appUrl.search = "";
    return NextResponse.redirect(appUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
