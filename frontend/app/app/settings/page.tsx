"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Button, Input, Select, Textarea, Skeleton, useToast, ConfirmModal } from "@/components/ui";

type Tab = "profile" | "samples" | "plan" | "account";

const tabs: { key: Tab; label: string }[] = [
  { key: "profile", label: "Profile" },
  { key: "samples", label: "Writing samples" },
  { key: "plan", label: "Plan & Credits" },
  { key: "account", label: "Account" },
];

const profileSchema = z.object({
  display_name: z.string().min(1),
  primary_category: z.string(),
  skills: z.string(),
  experience_level: z.enum(["junior", "mid", "senior"]),
  hourly_rate: z.coerce.number().min(1),
});

const pwSchema = z.object({
  current_password: z.string().min(1),
  new_password: z.string().min(8).regex(/\d/, "Must contain a number"),
});

const categories = [
  { value: "development", label: "Development" },
  { value: "design", label: "Design" },
  { value: "writing", label: "Writing" },
  { value: "marketing", label: "Marketing" },
  { value: "data", label: "Data" },
  { value: "other", label: "Other" },
];
const expLevels = [
  { value: "junior", label: "Junior" },
  { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" },
];

interface Sample { id: string; title: string; created_at: string; }

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");
  const { user, logout, refreshUser } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();
  const [deleteAccountConfirm, setDeleteAccountConfirm] = useState(false);
  const [newSample, setNewSample] = useState("");

  const profileForm = useForm({ resolver: zodResolver(profileSchema) });
  const pwForm = useForm({ resolver: zodResolver(pwSchema) });

  const { data: samples, isLoading: samplesLoading } = useQuery<Sample[]>({
    queryKey: ["samples"],
    queryFn: () => api.get("/me/samples"),
    enabled: tab === "samples",
  });

  const saveProfile = useMutation({
    mutationFn: (d: z.infer<typeof profileSchema>) => api.patch("/me/profile", {
      ...d,
      skills: d.skills.split(",").map((s) => s.trim()).filter(Boolean),
    }),
    onSuccess: () => { toast("Profile saved", "success"); refreshUser(); },
    onError: () => toast("Failed to save profile", "error"),
  });

  const addSample = useMutation({
    mutationFn: () => api.post("/me/samples", { content: newSample, title: "Sample" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["samples"] }); setNewSample(""); toast("Sample added", "success"); },
    onError: () => toast("Failed to add sample", "error"),
  });

  const deleteSample = useMutation({
    mutationFn: (id: string) => api.delete(`/me/samples/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["samples"] }); toast("Sample deleted", "success"); },
  });

  const changePassword = useMutation({
    mutationFn: (d: z.infer<typeof pwSchema>) => api.post("/auth/change-password", d),
    onSuccess: () => { toast("Password changed", "success"); pwForm.reset(); },
    onError: () => toast("Failed to change password — check current password", "error"),
  });

  async function handleDeleteAccount() {
    await api.delete("/me");
    await logout();
    router.push("/");
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="font-heading font-semibold text-xl text-[var(--text)] mb-6">Settings</h1>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-[var(--border)]">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-t-sm ${
              tab === key
                ? "text-[var(--accent)] border-b-2 border-[var(--accent)] -mb-px"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
            role="tab"
            aria-selected={tab === key}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Profile tab */}
      {tab === "profile" && (
        <form onSubmit={profileForm.handleSubmit((d) => saveProfile.mutate(d))} className="space-y-4">
          <Input label="Display name" defaultValue={user?.display_name} error={profileForm.formState.errors.display_name?.message} {...profileForm.register("display_name")} />
          <Select label="Primary category" options={categories} error={profileForm.formState.errors.primary_category?.message} {...profileForm.register("primary_category")} />
          <Input label="Skills (comma-separated)" error={profileForm.formState.errors.skills?.message} {...profileForm.register("skills")} />
          <Select label="Experience level" options={expLevels} error={profileForm.formState.errors.experience_level?.message} {...profileForm.register("experience_level")} />
          <Input label="Hourly rate (USD)" type="number" error={profileForm.formState.errors.hourly_rate?.message} {...profileForm.register("hourly_rate")} />
          <Button type="submit" loading={saveProfile.isPending}>Save profile</Button>
        </form>
      )}

      {/* Samples tab */}
      {tab === "samples" && (
        <div className="space-y-6">
          {samplesLoading ? <Skeleton className="h-24 w-full" /> : (
            <div className="space-y-2">
              {(samples ?? []).map((s) => (
                <div key={s.id} className="flex items-center justify-between bg-[var(--surface)] border border-[var(--border)] rounded-sm px-3 py-2">
                  <span className="text-sm text-[var(--text)]">{s.title}</span>
                  <Button variant="ghost" size="sm" onClick={() => deleteSample.mutate(s.id)}>Delete</Button>
                </div>
              ))}
            </div>
          )}
          <div className="space-y-2">
            <Textarea label="Add a writing sample" value={newSample} onChange={(e) => setNewSample(e.target.value)} rows={6} />
            <Button onClick={() => addSample.mutate()} loading={addSample.isPending} disabled={!newSample.trim()}>Add sample</Button>
          </div>
        </div>
      )}

      {/* Plan tab */}
      {tab === "plan" && (
        <div className="space-y-4">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-5 shadow-e1 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-heading font-semibold text-[var(--text)]">Free plan</h2>
              <span className="text-xs bg-[var(--surface-2)] border border-[var(--border)] px-2 py-0.5 rounded-sm text-[var(--text-muted)]">Current</span>
            </div>
            <div className="text-sm space-y-1 text-[var(--text-muted)]">
              <p>Drafts remaining: <strong className="text-[var(--text)]">{user?.credits_remaining ?? "—"}</strong> / 30</p>
              {user?.credits_reset_date && <p>Resets: {new Date(user.credits_reset_date).toLocaleDateString()}</p>}
            </div>
          </div>
          <div className="bg-[var(--accent-tint)] border border-[var(--accent)]/20 rounded-md p-5 space-y-2">
            <h3 className="font-heading font-semibold text-[var(--text)]">Pro plan — $19/mo</h3>
            <ul className="text-sm text-[var(--text-muted)] space-y-1 list-disc list-inside">
              <li>500 drafts/month</li>
              <li>Priority scoring</li>
              <li>Advanced analytics</li>
            </ul>
            <Button disabled className="mt-2">Upgrade to Pro — coming soon</Button>
            <p className="text-xs text-[var(--text-muted)]">Payment integration is coming after the demo. Contact us to get early access.</p>
          </div>
        </div>
      )}

      {/* Account tab */}
      {tab === "account" && (
        <div className="space-y-6">
          <form onSubmit={pwForm.handleSubmit((d) => changePassword.mutate(d))} className="space-y-4">
            <h2 className="font-heading font-semibold text-[var(--text)]">Change password</h2>
            <Input label="Current password" type="password" error={pwForm.formState.errors.current_password?.message} {...pwForm.register("current_password")} />
            <Input label="New password" type="password" error={pwForm.formState.errors.new_password?.message} {...pwForm.register("new_password")} />
            <Button type="submit" loading={changePassword.isPending}>Change password</Button>
          </form>
          <div className="pt-4 border-t border-[var(--border)] space-y-3">
            <Button variant="secondary" onClick={async () => { await logout(); router.push("/login"); }}>Sign out</Button>
            <div>
              <Button variant="danger" onClick={() => setDeleteAccountConfirm(true)}>Delete account</Button>
              <p className="text-xs text-[var(--text-muted)] mt-1">This permanently deletes your account and all data.</p>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={deleteAccountConfirm}
        onClose={() => setDeleteAccountConfirm(false)}
        onConfirm={handleDeleteAccount}
        title="Delete your account?"
        description="All your data, proposals, and samples will be permanently deleted. This cannot be undone."
        confirmLabel="Delete my account"
        danger
      />
    </div>
  );
}
