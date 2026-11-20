"use client";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { Skeleton, EmptyState } from "@/components/ui";

interface Stats {
  win_rate: number;
  total_proposals: number;
  won: number;
  lost: number;
  no_response: number;
  avg_score_won: number | null;
  avg_score_lost: number | null;
  credits_used: number;
  credits_limit: number;
  proposals_over_time: { date: string; count: number }[];
}

const CHART_COLORS = {
  won: "var(--success)",
  lost: "var(--danger)",
  "no-response": "var(--warn)",
  neutral: "var(--accent)",
};

const tooltipStyle = {
  backgroundColor: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "6px",
  color: "var(--text)",
  fontSize: "12px",
};

export default function DashboardPage() {
  const { data: stats, isLoading } = useQuery<Stats>({
    queryKey: ["stats"],
    queryFn: () => api.get("/me/stats"),
  });

  if (isLoading) return (
    <div className="max-w-content mx-auto px-4 py-6 space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );

  if (!stats || stats.total_proposals === 0) return (
    <div className="max-w-content mx-auto px-4 py-6">
      <h1 className="font-heading font-semibold text-xl text-[var(--text)] mb-6">Dashboard</h1>
      <EmptyState
        icon={TrendingUp}
        title="No data yet"
        description="Mark proposal outcomes to unlock your win-rate insights."
      />
    </div>
  );

  const outcomeData = [
    { name: "Won", value: stats.won, color: CHART_COLORS.won },
    { name: "Lost", value: stats.lost, color: CHART_COLORS.lost },
    { name: "No response", value: stats.no_response, color: CHART_COLORS["no-response"] },
  ].filter((d) => d.value > 0);

  const scoreData = [
    { name: "Won", score: stats.avg_score_won ?? 0 },
    { name: "Lost", score: stats.avg_score_lost ?? 0 },
  ];

  return (
    <div className="max-w-content mx-auto px-4 py-6 space-y-6">
      <h1 className="font-heading font-semibold text-xl text-[var(--text)]">Dashboard</h1>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Win rate", value: `${Math.round(stats.win_rate * 100)}%` },
          { label: "Total proposals", value: stats.total_proposals },
          { label: "Credits used", value: `${stats.credits_used} / ${stats.credits_limit}` },
          { label: "Avg score (won)", value: stats.avg_score_won ? Math.round(stats.avg_score_won) : "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-4 shadow-e1">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide">{label}</p>
            <p className="mt-1 text-2xl font-heading font-bold text-[var(--text)]">{value}</p>
          </div>
        ))}
      </div>

      {/* Proposals over time */}
      {stats.proposals_over_time.length > 1 && (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1">
          <h2 className="font-heading font-semibold text-sm text-[var(--text)] mb-4">Proposals sent over time</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={stats.proposals_over_time}>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="count" stroke="var(--accent)" strokeWidth={2} dot={false} name="Proposals" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        {/* Outcome breakdown */}
        {outcomeData.length > 0 && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1">
            <h2 className="font-heading font-semibold text-sm text-[var(--text)] mb-4">Outcome breakdown</h2>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={outcomeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={(e) => `${e.name}: ${e.value}`} labelLine={false}>
                  {outcomeData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Avg score won vs lost */}
        {(stats.avg_score_won || stats.avg_score_lost) && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1">
            <h2 className="font-heading font-semibold text-sm text-[var(--text)] mb-4">Avg score: won vs lost</h2>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={scoreData}>
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="score" fill="var(--accent)" radius={[4, 4, 0, 0]} name="Score" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
