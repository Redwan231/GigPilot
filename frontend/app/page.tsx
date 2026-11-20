import Link from "next/link";
import { Zap, Target, TrendingUp } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      {/* Nav */}
      <header className="border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-content mx-auto px-4 h-14 flex items-center justify-between">
          <span className="font-heading font-bold text-lg text-[var(--accent)]">GigPilot</span>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-[var(--text-muted)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm px-2 py-1">
              Log in
            </Link>
            <Link
              href="/signup"
              className="inline-flex items-center px-4 py-2 rounded-sm bg-[var(--accent)] text-[var(--accent-contrast)] text-sm font-medium hover:bg-brand-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-content mx-auto px-4 pt-20 pb-16 text-center">
        <h1 className="font-heading font-bold text-5xl leading-tight text-[var(--text)] mb-4" style={{ textWrap: "balance" }}>
          Your AI co-pilot for <span className="text-[var(--accent)]">freelance jobs</span>
        </h1>
        <p className="text-lg text-[var(--text-muted)] mb-8 max-w-xl mx-auto">
          Discover jobs across platforms, score your fit, and generate proposals in your own voice — all in one place.
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link
            href="/signup"
            className="inline-flex items-center px-6 py-3 rounded-sm bg-[var(--accent)] text-[var(--accent-contrast)] font-medium hover:bg-brand-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          >
            Get started free
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center px-6 py-3 rounded-sm border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] font-medium hover:bg-[var(--surface-2)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          >
            Log in
          </Link>
        </div>
      </section>

      {/* Value props */}
      <section className="max-w-content mx-auto px-4 pb-20">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Zap, title: "Discover", body: "Jobs from RemoteOK, Remotive, Himalayas, and WeWorkRemotely — aggregated in one clean feed." },
            { icon: Target, title: "Score & Filter", body: "AI scores each job against your skills, rate, and experience. Focus on the ones you can actually win." },
            { icon: TrendingUp, title: "Learn", body: "Track won/lost outcomes. Your scoring recalibrates over time so the feed keeps getting better." },
          ].map(({ icon: Icon, title, body }) => (
            <div key={title} className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-6 shadow-e1">
              <Icon className="h-8 w-8 text-[var(--accent)] mb-3" aria-hidden="true" />
              <h3 className="font-heading font-semibold text-lg text-[var(--text)] mb-2">{title}</h3>
              <p className="text-sm text-[var(--text-muted)]">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-content mx-auto px-4 pb-20">
        <h2 className="font-heading font-bold text-3xl text-center text-[var(--text)] mb-8">Simple pricing</h2>
        <div className="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto">
          {[
            { tier: "Free", price: "$0", features: ["30 AI drafts/month", "Daily scoring", "All 4 platforms", "Win/loss tracking"] },
            { tier: "Pro", price: "$19/mo", features: ["500 AI drafts/month", "Unlimited scoring", "Priority AI", "Advanced analytics"], accent: true },
          ].map(({ tier, price, features, accent }) => (
            <div key={tier} className={`rounded-md p-6 border shadow-e1 ${accent ? "bg-[var(--accent-tint)] border-[var(--accent)]/30" : "bg-[var(--surface)] border-[var(--border)]"}`}>
              <h3 className="font-heading font-bold text-xl text-[var(--text)]">{tier}</h3>
              <p className="text-3xl font-heading font-bold text-[var(--text)] mt-1">{price}</p>
              <ul className="mt-4 space-y-2">
                {features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                    <span className="text-[var(--accent)]">✓</span> {f}
                  </li>
                ))}
              </ul>
              {accent && <p className="mt-3 text-xs text-[var(--text-muted)]">Coming after demo launch.</p>}
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-[var(--border)] py-6 text-center text-sm text-[var(--text-muted)]">
        © 2026 GigPilot · Built with ❤️ at Daffodil International University
      </footer>
    </div>
  );
}
