"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Button, Input, Select, Textarea } from "@/components/ui";

const profileSchema = z.object({
  display_name: z.string().min(1, "Required"),
  primary_category: z.string().min(1, "Required"),
  skills: z.string().min(1, "Enter at least 3 skills"),
  experience_level: z.enum(["junior", "mid", "senior"]),
  hourly_rate: z.coerce.number().min(1, "Required"),
});

const categories = [
  { value: "development", label: "Software Development" },
  { value: "design", label: "Design" },
  { value: "writing", label: "Writing & Content" },
  { value: "marketing", label: "Marketing" },
  { value: "data", label: "Data & Analytics" },
  { value: "other", label: "Other" },
];

const expLevels = [
  { value: "junior", label: "Junior (< 2 years)" },
  { value: "mid", label: "Mid (2–5 years)" },
  { value: "senior", label: "Senior (5+ years)" },
];

const tones = [
  { value: "formal", label: "Formal" },
  { value: "friendly", label: "Friendly" },
  { value: "direct", label: "Direct" },
];
const lengths = [
  { value: "short", label: "Short (< 150 words)" },
  { value: "medium", label: "Medium (150–300 words)" },
  { value: "long", label: "Long (300+ words)" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [samplesText, setSamplesText] = useState("");
  const [samplesSkipped, setSamplesSkipped] = useState(false);
  const [stylePrefs, setStylePrefs] = useState({ tone: "friendly", length: "medium", greeting: "Hi" });
  const [submitting, setSubmitting] = useState(false);

  const form = useForm({ resolver: zodResolver(profileSchema) });

  async function handleProfileNext(data: z.infer<typeof profileSchema>) {
    try {
      await api.patch("/me/profile", {
        display_name: data.display_name,
        primary_category: data.primary_category,
        skills: data.skills.split(",").map((s) => s.trim()).filter(Boolean),
        experience_level: data.experience_level,
        hourly_rate: data.hourly_rate,
      });
      setStep(2);
    } catch {
      form.setError("root" as never, { message: "Failed to save profile." } as never);
    }
  }

  async function handleFinish() {
    setSubmitting(true);
    try {
      if (samplesText.trim()) {
        await api.post("/me/samples", { content: samplesText.trim(), title: "Onboarding sample" });
      }
      await api.patch("/me/profile", {
        profile_complete: true,
        ...(samplesSkipped ? { cold_start_prefs: stylePrefs } : {}),
      });
      await refreshUser();
      router.push("/app");
    } catch {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="mb-6 text-center">
          <span className="font-heading font-bold text-2xl text-[var(--accent)]">GigPilot</span>
          <p className="text-sm text-[var(--text-muted)] mt-1">Step {step} of {samplesSkipped ? 3 : 2}</p>
          <div className="mt-3 flex gap-2">
            {[1, 2, ...(samplesSkipped ? [3] : [])].map((s) => (
              <div key={s} className={`flex-1 h-1 rounded-full ${s <= step ? "bg-[var(--accent)]" : "bg-[var(--border)]"}`} />
            ))}
          </div>
        </div>

        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-6 shadow-e1">
          {step === 1 && (
            <form onSubmit={form.handleSubmit(handleProfileNext)} className="space-y-4">
              <h2 className="font-heading font-semibold text-lg text-[var(--text)]">Your profile</h2>
              <Input label="Display name" error={form.formState.errors.display_name?.message} {...form.register("display_name")} />
              <Select label="Primary category" options={categories} placeholder="Select…" error={form.formState.errors.primary_category?.message} {...form.register("primary_category")} />
              <Input label="Skills (comma-separated, min 3)" placeholder="React, TypeScript, Node.js" error={form.formState.errors.skills?.message} {...form.register("skills")} />
              <Select label="Experience level" options={expLevels} error={form.formState.errors.experience_level?.message} {...form.register("experience_level")} />
              <Input label="Hourly rate (USD)" type="number" min={1} error={form.formState.errors.hourly_rate?.message} {...form.register("hourly_rate")} />
              <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>Continue</Button>
            </form>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="font-heading font-semibold text-lg text-[var(--text)]">Writing samples</h2>
              <p className="text-sm text-[var(--text-muted)]">Paste 1–5 past proposals so GigPilot can match your voice.</p>
              <Textarea
                label="Paste a past proposal"
                placeholder="Paste your writing sample here…"
                rows={8}
                value={samplesText}
                onChange={(e) => setSamplesText(e.target.value)}
              />
              <div className="flex gap-3">
                <Button variant="secondary" className="flex-1" onClick={() => { setSamplesSkipped(true); setStep(3); }}>
                  I&rsquo;ll do this later
                </Button>
                <Button className="flex-1" onClick={handleFinish} loading={submitting}>Finish setup</Button>
              </div>
              {samplesSkipped === false && (
                <p className="text-xs text-[var(--text-muted)]">Skipping means drafts won&rsquo;t be voice-matched until you add samples.</p>
              )}
            </div>
          )}

          {step === 3 && samplesSkipped && (
            <div className="space-y-4">
              <h2 className="font-heading font-semibold text-lg text-[var(--text)]">Your writing style</h2>
              <p className="text-sm text-[var(--text-muted)] bg-warn/10 border border-warn/20 rounded-sm px-3 py-2">
                You skipped samples — drafts will use this questionnaire until you add samples in Settings.
              </p>
              <Select label="Tone" options={tones} value={stylePrefs.tone} onChange={(e) => setStylePrefs((p) => ({ ...p, tone: e.target.value }))} />
              <Select label="Proposal length" options={lengths} value={stylePrefs.length} onChange={(e) => setStylePrefs((p) => ({ ...p, length: e.target.value }))} />
              <Input label="Preferred greeting" placeholder="Hi / Hello / Dear" value={stylePrefs.greeting} onChange={(e) => setStylePrefs((p) => ({ ...p, greeting: e.target.value }))} />
              <div className="flex gap-3">
                <Button variant="secondary" onClick={() => setStep(2)}>Back</Button>
                <Button className="flex-1" onClick={handleFinish} loading={submitting}>Finish setup</Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
