"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, Briefcase, FileText, Settings, LogOut, Menu, X, Zap } from "lucide-react";
import { useAuth } from "@/lib/auth";

const nav = [
  { href: "/app", icon: Briefcase, label: "Jobs" },
  { href: "/app/proposals", icon: FileText, label: "Proposals" },
  { href: "/app/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/app/settings", icon: Settings, label: "Settings" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => { setSidebarOpen(false); }, [pathname]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const credits = user?.credits_remaining ?? "—";

  const NavLinks = () => (
    <nav className="flex flex-col gap-1 flex-1">
      {nav.map(({ href, icon: Icon, label }) => {
        const active = href === "/app" ? pathname === "/app" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`
              flex items-center gap-3 px-3 py-2 rounded-sm text-sm font-medium transition-colors
              ${active
                ? "border-l-2 border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-tint)] pl-[10px]"
                : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] border-l-2 border-transparent"
              }
            `}
            aria-current={active ? "page" : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-56 bg-[var(--surface)] border-r border-[var(--border)] p-4 shrink-0">
        <div className="mb-6">
          <span className="font-heading font-bold text-lg text-[var(--accent)]">GigPilot</span>
        </div>
        <NavLinks />
        <div className="mt-4 pt-4 border-t border-[var(--border)] space-y-3">
          <div className="flex items-center gap-2 text-sm">
            <Zap className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
            <span className="text-[var(--text-muted)]">Credits:</span>
            <span className="font-medium text-[var(--text)]">{credits}</span>
          </div>
          <div className="text-xs text-[var(--text-muted)] truncate">{user?.email}</div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-danger transition-colors w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="md:hidden fixed top-0 inset-x-0 z-40 flex items-center justify-between px-4 h-14 bg-[var(--surface)] border-b border-[var(--border)]">
        <span className="font-heading font-bold text-[var(--accent)]">GigPilot</span>
        <div className="flex items-center gap-3">
          <span className="text-sm text-[var(--text-muted)]">
            <Zap className="inline h-3 w-3 mr-1 text-[var(--accent)]" aria-hidden="true" />
            {credits}
          </span>
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label={sidebarOpen ? "Close menu" : "Open menu"}
            className="text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile nav drawer */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-30 pt-14">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <div className="relative bg-[var(--surface)] h-full w-56 p-4 flex flex-col border-r border-[var(--border)]">
            <NavLinks />
            <button onClick={handleLogout} className="flex items-center gap-2 mt-4 text-sm text-[var(--text-muted)] hover:text-danger">
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-y-auto md:pt-0 pt-14">
        {children}
      </main>
    </div>
  );
}
