"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Badge, Skeleton, Textarea, useToast, ConfirmModal } from "@/components/ui";
import { formatDistanceToNow } from "@/lib/utils";

interface ProposalDetail {
  id: string;
  job_id: string;
  job_title: string;
  platform: string;
  content: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const STATUS_OPTIONS = [
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
  { value: "no-response", label: "No response" },
];

export default function ProposalDetailPage() {
  const { proposalId } = useParams<{ proposalId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const { data: proposal, isLoading } = useQuery<ProposalDetail>({
    queryKey: ["proposal", proposalId],
    queryFn: () => api.get(`/proposals/${proposalId}`),
  });

  const [content, setContent] = useState("");
  const [edited, setEdited] = useState(false);

  const saveMutation = useMutation({
    mutationFn: () => api.patch(`/proposals/${proposalId}`, { content }),
    onSuccess: () => { toast("Saved", "success"); setEdited(false); },
  });

  const outcomeMutation = useMutation({
    mutationFn: (status: string) => api.patch(`/proposals/${proposalId}`, { status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["proposal", proposalId] }); toast("Outcome saved", "success"); },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/proposals/${proposalId}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["proposals"] }); router.push("/app/proposals"); },
  });

  if (isLoading) return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
      <Skeleton className="h-6 w-1/2" />
      <Skeleton className="h-48 w-full" />
    </div>
  );

  if (!proposal) return null;

  const displayContent = edited ? content : proposal.content;

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back
      </button>

      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1 space-y-3">
        <h1 className="font-heading font-bold text-lg text-[var(--text)]">{proposal.job_title}</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="platform">{proposal.platform}</Badge>
          <Badge variant={proposal.status as "won" | "lost" | "no-response" | "draft" | "used"}>{proposal.status}</Badge>
          <span className="text-xs text-[var(--text-muted)]">Updated {formatDistanceToNow(proposal.updated_at)}</span>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {STATUS_OPTIONS.map((s) => (
            <Button
              key={s.value}
              variant={proposal.status === s.value ? "primary" : "secondary"}
              size="sm"
              onClick={() => outcomeMutation.mutate(s.value)}
              loading={outcomeMutation.isPending}
            >
              {s.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1 space-y-4">
        <h2 className="font-heading font-semibold text-[var(--text)]">Proposal text</h2>
        <Textarea
          label="Content"
          srLabel
          value={displayContent}
          onChange={(e) => { setContent(e.target.value); setEdited(true); }}
          rows={12}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => saveMutation.mutate()}
            loading={saveMutation.isPending}
            disabled={!edited}
          >
            Save
          </Button>
          <Button variant="danger" size="sm" onClick={() => setDeleteConfirm(true)}>Delete</Button>
        </div>
      </div>

      <ConfirmModal
        open={deleteConfirm}
        onClose={() => setDeleteConfirm(false)}
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
        title="Delete proposal?"
        description="This cannot be undone."
        confirmLabel="Delete"
        danger
      />
    </div>
  );
}
