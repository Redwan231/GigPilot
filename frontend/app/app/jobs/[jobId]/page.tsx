"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ExternalLink, ChevronDown, ChevronUp, Copy, Download, RefreshCw, ArrowLeft } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Badge, ScoreChip, Skeleton, useToast, ConfirmModal } from "@/components/ui";

interface JobDetail {
  id: string;
  title: string;
  platform: string;
  description: string;
  source_url: string;
  budget_min?: number;
  budget_max?: number;
  budget_type?: string;
  skills: string[];
  posted_at: string;
  score?: number;
  score_dimensions?: { skills: number; seniority: number; rate: number; freshness: number };
}

interface ScoreResult {
  score: number;
  dimensions: { skills: number; seniority: number; rate: number; freshness: number };
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { user, refreshUser } = useAuth();
  const { toast } = useToast();
  const [whyOpen, setWhyOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [regenConfirm, setRegenConfirm] = useState(false);

  const { data: job, isLoading, isError } = useQuery<JobDetail>({
    queryKey: ["job", jobId],
    queryFn: () => api.get(`/jobs/${jobId}`),
  });

  const { data: whyData, isFetching: whyLoading } = useQuery<{ reasoning: string }>({
    queryKey: ["job-why", jobId],
    queryFn: () => api.get(`/jobs/${jobId}/score/why`),
    enabled: whyOpen && !!job?.score,
  });

  const scoreMutation = useMutation({
    mutationFn: () => api.post<ScoreResult>(`/jobs/${jobId}/score`),
    onSuccess: (result) => {
      qc.setQueryData<JobDetail>(["job", jobId], (old) =>
        old ? { ...old, score: result.score, score_dimensions: result.dimensions } : old
      );
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 429) toast("Daily scoring limit reached.", "error");
      else toast("Scoring failed. Please retry.", "error");
    },
  });

  const draftMutation = useMutation({
    mutationFn: () => api.post<{ content: string }>(`/jobs/${jobId}/draft`),
    onSuccess: (result) => {
      setDraft(result.content);
      refreshUser();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 402) toast("No credits remaining.", "error");
      else toast("Draft failed — your credit was not charged. Retry.", "error");
    },
  });

  const markUsedMutation = useMutation({
    mutationFn: () => api.post(`/proposals`, { job_id: jobId, content: draft }),
    onSuccess: () => {
      toast("Proposal saved!", "success");
      router.push("/app/proposals");
    },
  });

  function handleCopy() {
    navigator.clipboard.writeText(draft);
    toast("Copied to clipboard", "success");
  }

  function handleExport(fmt: "txt" | "md") {
    const blob = new Blob([draft], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `proposal.${fmt}`;
    a.click();
  }

  if (isLoading) return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-4 w-1/4" />
      <Skeleton className="h-48 w-full" />
    </div>
  );

  if (isError || !job) return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <p className="text-danger">Failed to load job.</p>
      <Button variant="secondary" size="sm" className="mt-2" onClick={() => router.back()}>Go back</Button>
    </div>
  );

  const credits = user?.credits_remaining ?? 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back
      </button>

      {/* Header */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <h1 className="font-heading font-bold text-xl text-[var(--text)]">{job.title}</h1>
          {job.score != null && <ScoreChip score={job.score} size="lg" />}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="platform">{job.platform}</Badge>
          {(job.budget_min || job.budget_max) && (
            <span className="text-sm text-[var(--text-muted)]">
              ${job.budget_min ?? "?"}–${job.budget_max ?? "?"}{job.budget_type === "hourly" ? "/hr" : ""}
            </span>
          )}
          <a
            href={job.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm"
          >
            View original <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        </div>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {job.skills.map((s) => (
            <span key={s} className="text-xs px-1.5 py-0.5 rounded-sm bg-[var(--surface-2)] text-[var(--text-muted)]">{s}</span>
          ))}
        </div>
        <p className="text-sm text-[var(--text)] whitespace-pre-wrap leading-relaxed">{job.description}</p>
      </div>

      {/* Score panel */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1 space-y-4">
        <h2 className="font-heading font-semibold text-[var(--text)]">Fit score</h2>
        {!job.score ? (
          <Button onClick={() => scoreMutation.mutate()} loading={scoreMutation.isPending}>
            {scoreMutation.isPending ? "Scoring…" : "Score this job"}
          </Button>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(job.score_dimensions ?? {}).map(([dim, val]) => (
                <div key={dim} className="space-y-1">
                  <div className="flex justify-between text-xs text-[var(--text-muted)] capitalize">
                    <span>{dim}</span><span>{val}/25</span>
                  </div>
                  <div className="h-1.5 bg-[var(--surface-2)] rounded-full overflow-hidden">
                    <div className="h-full bg-[var(--accent)] rounded-full transition-all" style={{ width: `${(val / 25) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <button
              className="flex items-center gap-1 text-sm text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm"
              onClick={() => setWhyOpen((v) => !v)}
            >
              {whyOpen ? <ChevronUp className="h-4 w-4" aria-hidden="true" /> : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
              Why this score?
            </button>
            {whyOpen && (
              whyLoading
                ? <Skeleton className="h-20 w-full" />
                : <p className="text-sm text-[var(--text-muted)] bg-[var(--surface-2)] rounded-sm p-3">{whyData?.reasoning}</p>
            )}
          </>
        )}
      </div>

      {/* Draft panel */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading font-semibold text-[var(--text)]">Proposal draft</h2>
          <span className="text-xs text-[var(--text-muted)]">{credits} credit{credits !== 1 ? "s" : ""} remaining</span>
        </div>

        {credits === 0 && !draft ? (
          <div className="text-sm text-[var(--text-muted)] bg-warn/10 border border-warn/20 rounded-sm p-3">
            You&rsquo;ve used all your drafts this month.{" "}
            <a href="/app/settings" className="text-[var(--accent)] underline">Upgrade to Pro for 500/month</a>.
          </div>
        ) : !draft ? (
          <Button onClick={() => draftMutation.mutate()} loading={draftMutation.isPending} disabled={credits === 0}>
            {draftMutation.isPending ? "Drafting in your voice…" : "Generate proposal"}
          </Button>
        ) : (
          <div className="space-y-3">
            <textarea
              className="w-full min-h-[200px] bg-[var(--surface-2)] border border-[var(--border)] rounded-sm p-3 text-sm text-[var(--text)] resize-y focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Proposal draft"
            />
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" size="sm" onClick={handleCopy}><Copy className="h-3.5 w-3.5 mr-1" aria-hidden="true" />Copy</Button>
              <Button variant="ghost" size="sm" onClick={() => handleExport("txt")}><Download className="h-3.5 w-3.5 mr-1" aria-hidden="true" />.txt</Button>
              <Button variant="ghost" size="sm" onClick={() => handleExport("md")}><Download className="h-3.5 w-3.5 mr-1" aria-hidden="true" />.md</Button>
              <Button variant="ghost" size="sm" onClick={() => setRegenConfirm(true)}>
                <RefreshCw className="h-3.5 w-3.5 mr-1" aria-hidden="true" />Regenerate
              </Button>
              <Button size="sm" onClick={() => markUsedMutation.mutate()} loading={markUsedMutation.isPending}>Mark as used</Button>
            </div>
          </div>
        )}
      </div>

      <ConfirmModal
        open={regenConfirm}
        onClose={() => setRegenConfirm(false)}
        onConfirm={() => { setRegenConfirm(false); draftMutation.mutate(); }}
        title="Regenerate proposal?"
        description="This will consume 1 more credit from your monthly quota."
        confirmLabel="Regenerate (−1 credit)"
      />
    </div>
  );
}
