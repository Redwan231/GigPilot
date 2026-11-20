"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Search, SlidersHorizontal, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, Badge, ScoreChip, SkeletonCard, EmptyState } from "@/components/ui";
import { useToast } from "@/components/ui";
import { formatDistanceToNow } from "@/lib/utils";

interface Job {
  id: string;
  title: string;
  platform: string;
  snippet: string;
  budget_min?: number;
  budget_max?: number;
  budget_type?: string;
  skills: string[];
  posted_at: string;
  score?: number;
}

interface Filters {
  platform: string;
  sort: "newest" | "score";
  min_score: string;
}

export default function JobFeedPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();
  const [filters, setFilters] = useState<Filters>({ platform: "", sort: "newest", min_score: "" });
  const [filtersOpen, setFiltersOpen] = useState(false);

  const params = new URLSearchParams();
  if (filters.platform) params.set("platform", filters.platform);
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.min_score) params.set("min_score", filters.min_score);
  params.set("limit", "20");

  const { data, isLoading, isError, error, refetch } = useQuery<{ items: Job[] }>({
    queryKey: ["jobs", filters],
    queryFn: () => api.get(`/jobs?${params}`),
  });

  const scoreMutation = useMutation({
    mutationFn: (jobId: string) => api.post<{ score: number }>(`/jobs/${jobId}/score`),
    onSuccess: (result, jobId) => {
      qc.setQueryData<{ items: Job[] }>(["jobs", filters], (old) => ({
        items: (old?.items ?? []).map((j) => j.id === jobId ? { ...j, score: result.score } : j),
      }));
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 429) {
        toast("Daily scoring limit reached. Resets tomorrow.", "error");
      } else {
        toast("Scoring failed. Please retry.", "error");
      }
    },
  });

  const jobs = data?.items ?? [];

  return (
    <div className="max-w-content mx-auto px-4 py-6">
      {/* Top bar */}
      <div className="flex items-center gap-3 mb-6">
        <h1 className="font-heading font-semibold text-xl text-[var(--text)] flex-1">Jobs</h1>
        <button
          onClick={() => setFiltersOpen((v) => !v)}
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm px-2 py-1 border border-[var(--border)] bg-[var(--surface)]"
          aria-expanded={filtersOpen}
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
          Filters
        </button>
        <select
          className="text-sm bg-[var(--surface)] border border-[var(--border)] rounded-sm px-2 py-1 text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          value={filters.sort}
          onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value as "newest" | "score" }))}
          aria-label="Sort"
        >
          <option value="newest">Newest</option>
          <option value="score">Best match</option>
        </select>
      </div>

      {/* Filter rail */}
      {filtersOpen && (
        <div className="mb-6 p-4 bg-[var(--surface)] border border-[var(--border)] rounded-md flex flex-wrap gap-4 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--text-muted)]">Platform</label>
            <select
              className="text-sm bg-[var(--surface-2)] border border-[var(--border)] rounded-sm px-2 py-1.5 text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              value={filters.platform}
              onChange={(e) => setFilters((f) => ({ ...f, platform: e.target.value }))}
            >
              <option value="">All platforms</option>
              <option value="remoteok">RemoteOK</option>
              <option value="remotive">Remotive</option>
              <option value="himalayas">Himalayas</option>
              <option value="weworkremotely">WeWorkRemotely</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--text-muted)]">Min score</label>
            <input
              type="number" min={0} max={100} placeholder="0"
              className="w-20 text-sm bg-[var(--surface-2)] border border-[var(--border)] rounded-sm px-2 py-1.5 text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              value={filters.min_score}
              onChange={(e) => setFilters((f) => ({ ...f, min_score: e.target.value }))}
            />
          </div>
          <Button variant="ghost" size="sm" onClick={() => setFilters({ platform: "", sort: "newest", min_score: "" })}>
            Reset
          </Button>
        </div>
      )}

      {/* States */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {isError && (
        <div className="p-6 bg-danger/10 border border-danger/20 rounded-md text-sm text-danger flex items-center justify-between">
          <span>Failed to load jobs. {(error as ApiError)?.message}</span>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>Retry</Button>
        </div>
      )}

      {!isLoading && !isError && jobs.length === 0 && (
        <EmptyState
          icon={Search}
          title={filters.platform || filters.min_score ? "No jobs match these filters" : "Fetching jobs…"}
          description={filters.platform || filters.min_score ? undefined : "We're fetching fresh jobs — check back in a few minutes."}
          action={filters.platform || filters.min_score
            ? { label: "Reset filters", onClick: () => setFilters({ platform: "", sort: "newest", min_score: "" }) }
            : { label: "Refresh", onClick: () => refetch() }
          }
        />
      )}

      {!isLoading && !isError && jobs.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-4 shadow-e1 cursor-pointer hover:border-[var(--accent)]/40 transition-colors flex flex-col gap-3"
              onClick={() => router.push(`/app/jobs/${job.id}`)}
              role="article"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") router.push(`/app/jobs/${job.id}`); }}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-heading font-semibold text-sm text-[var(--text)] line-clamp-2 flex-1">{job.title}</h3>
                {job.score != null
                  ? <ScoreChip score={job.score} size="sm" />
                  : (
                    <button
                      className="text-xs text-[var(--accent)] border border-[var(--accent)]/30 rounded-sm px-2 py-0.5 hover:bg-[var(--accent-tint)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                      onClick={(e) => { e.stopPropagation(); scoreMutation.mutate(job.id); }}
                      disabled={scoreMutation.isPending}
                      aria-label={`Score ${job.title}`}
                    >
                      {scoreMutation.isPending && scoreMutation.variables === job.id ? "Scoring…" : "Score"}
                    </button>
                  )
                }
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="platform">{job.platform}</Badge>
                {(job.budget_min || job.budget_max) && (
                  <span className="text-xs text-[var(--text-muted)]">
                    ${job.budget_min ?? "?"}–${job.budget_max ?? "?"}
                    {job.budget_type === "hourly" ? "/hr" : ""}
                  </span>
                )}
              </div>
              <p className="text-xs text-[var(--text-muted)] line-clamp-2">{job.snippet}</p>
              <div className="flex flex-wrap gap-1.5">
                {job.skills.slice(0, 4).map((s) => (
                  <span key={s} className="text-xs px-1.5 py-0.5 rounded-sm bg-[var(--surface-2)] text-[var(--text-muted)]">{s}</span>
                ))}
                {job.skills.length > 4 && (
                  <span className="text-xs text-[var(--text-muted)]">+{job.skills.length - 4}</span>
                )}
              </div>
              <p className="text-xs text-[var(--text-muted)] mt-auto">{formatDistanceToNow(job.posted_at)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
