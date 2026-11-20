"use client";
import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center p-4 text-center">
      <AlertTriangle className="h-12 w-12 text-danger mb-4" aria-hidden="true" />
      <h1 className="font-heading font-bold text-2xl text-[var(--text)] mb-2">Something went wrong</h1>
      <p className="text-[var(--text-muted)] mb-6 max-w-sm">An unexpected error occurred. Please try again or contact support if the issue persists.</p>
      <button
        onClick={reset}
        className="inline-flex items-center px-4 py-2 rounded-sm bg-[var(--accent)] text-[var(--accent-contrast)] text-sm font-medium hover:bg-brand-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        Try again
      </button>
    </div>
  );
}
