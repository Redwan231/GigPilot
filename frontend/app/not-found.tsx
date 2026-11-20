import Link from "next/link";
import { SearchX } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center p-4 text-center">
      <SearchX className="h-12 w-12 text-[var(--text-muted)] mb-4" aria-hidden="true" />
      <h1 className="font-heading font-bold text-4xl text-[var(--text)] mb-2">404</h1>
      <p className="text-[var(--text-muted)] mb-6">This page doesn&rsquo;t exist.</p>
      <Link
        href="/"
        className="inline-flex items-center px-4 py-2 rounded-sm bg-[var(--accent)] text-[var(--accent-contrast)] text-sm font-medium hover:bg-brand-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        Go home
      </Link>
    </div>
  );
}
