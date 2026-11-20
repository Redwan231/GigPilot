"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { FileText } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Badge, EmptyState, SkeletonCard, Button, useToast } from "@/components/ui";
import { formatDistanceToNow } from "@/lib/utils";

interface Proposal {
  id: string;
  job_id: string;
  job_title: string;
  platform: string;
  status: "draft" | "used" | "won" | "lost" | "no-response";
  created_at: string;
}

const STATUS_OPTIONS = ["won", "lost", "no-response"] as const;

export default function ProposalsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading, isError } = useQuery<{ items: Proposal[] }>({
    queryKey: ["proposals"],
    queryFn: () => api.get("/proposals"),
  });

  const outcomeMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/proposals/${id}`, { status }),
    onSuccess: (_, vars) => {
      qc.setQueryData<{ items: Proposal[] }>(["proposals"], (old) => ({
        items: (old?.items ?? []).map((p) => p.id === vars.id ? { ...p, status: vars.status as Proposal["status"] } : p),
      }));
      toast("Outcome saved", "success");
    },
  });

  const proposals = data?.items ?? [];

  if (isLoading) return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
      {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="font-heading font-semibold text-xl text-[var(--text)] mb-6">Proposals</h1>

      {isError && <p className="text-danger text-sm mb-4">Failed to load proposals.</p>}

      {proposals.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No proposals yet"
          description="Find a job and generate your first draft."
          action={{ label: "Browse jobs", onClick: () => router.push("/app") }}
        />
      ) : (
        <div className="space-y-3">
          {proposals.map((p) => (
            <div
              key={p.id}
              className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-4 shadow-e1 flex items-center gap-4"
            >
              <div
                className="flex-1 min-w-0 cursor-pointer"
                onClick={() => router.push(`/app/proposals/${p.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") router.push(`/app/proposals/${p.id}`); }}
              >
                <p className="font-medium text-sm text-[var(--text)] truncate">{p.job_title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="platform">{p.platform}</Badge>
                  <Badge variant={p.status}>{p.status.replace("-", " ")}</Badge>
                  <span className="text-xs text-[var(--text-muted)]">{formatDistanceToNow(p.created_at)}</span>
                </div>
              </div>
              {p.status === "used" || p.status === "draft" ? (
                <select
                  className="text-xs bg-[var(--surface-2)] border border-[var(--border)] rounded-sm px-2 py-1 text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  value=""
                  onChange={(e) => { if (e.target.value) outcomeMutation.mutate({ id: p.id, status: e.target.value }); }}
                  aria-label="Set outcome"
                >
                  <option value="">Set outcome…</option>
                  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.replace("-", " ")}</option>)}
                </select>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
