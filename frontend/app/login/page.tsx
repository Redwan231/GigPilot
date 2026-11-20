"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { Suspense } from "react";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(1, "Password is required"),
});
type FormData = z.infer<typeof schema>;

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const expired = params.get("expired") === "1";
  const next = params.get("next") || "/app";

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  async function onSubmit(data: FormData) {
    try {
      await login(data.email, data.password);
      router.push(next);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError("root", { message: "Email or password is incorrect." });
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
          <h1 className="mt-2 text-xl font-heading font-semibold text-[var(--text)]">Sign in to your account</h1>
          {expired && (
            <p className="mt-2 text-sm text-warn">Your session expired, please log in again.</p>
          )}
        </div>
        <form onSubmit={handleSubmit(onSubmit)} className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-6 shadow-e1 space-y-4">
          {errors.root && (
            <p className="text-sm text-danger bg-danger/10 border border-danger/20 rounded-sm px-3 py-2">
              {errors.root.message}
            </p>
          )}
          <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
          <Input label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register("password")} />
          <Button type="submit" className="w-full" loading={isSubmitting}>Sign in</Button>
        </form>
        <p className="mt-4 text-center text-sm text-[var(--text-muted)]">
          Don&rsquo;t have an account?{" "}
          <Link href="/signup" className="text-[var(--accent)] hover:underline">Sign up</Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
