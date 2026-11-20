"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Min 8 characters").regex(/\d/, "Must contain a number"),
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});
type FormData = z.infer<typeof schema>;

export default function SignupPage() {
  const { signup } = useAuth();
  const router = useRouter();

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  async function onSubmit(data: FormData) {
    try {
      await signup(data.email, data.password);
      router.push("/onboarding");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("email", { message: "An account with this email already exists." });
      } else {
        setError("root", { message: "Something went wrong. Please try again." });
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[var(--bg)]">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="font-heading font-bold text-2xl text-[var(--accent)]">GigPilot</span>
          <h1 className="mt-2 text-xl font-heading font-semibold text-[var(--text)]">Create your account</h1>
        </div>
        <form onSubmit={handleSubmit(onSubmit)} className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-6 shadow-e1 space-y-4">
          {errors.root && (
            <p className="text-sm text-danger bg-danger/10 border border-danger/20 rounded-sm px-3 py-2">
              {errors.root.message}
            </p>
          )}
          <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
          <Input label="Password" type="password" autoComplete="new-password" error={errors.password?.message} {...register("password")} />
          <Input label="Confirm password" type="password" autoComplete="new-password" error={errors.confirmPassword?.message} {...register("confirmPassword")} />
          <Button type="submit" className="w-full" loading={isSubmitting}>Create account</Button>
        </form>
        <p className="mt-4 text-center text-sm text-[var(--text-muted)]">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--accent)] hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
