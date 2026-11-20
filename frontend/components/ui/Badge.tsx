type BadgeVariant = "platform" | "draft" | "used" | "won" | "lost" | "no-response" | "default";

const styles: Record<BadgeVariant, string> = {
  platform: "bg-[var(--surface-2)] text-[var(--text-muted)]",
  draft: "bg-[var(--surface-2)] text-[var(--text-muted)]",
  used: "bg-info/10 text-info",
  won: "bg-success/10 text-success",
  lost: "bg-danger/10 text-danger",
  "no-response": "bg-warn/10 text-warn",
  default: "bg-[var(--surface-2)] text-[var(--text-muted)]",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium uppercase tracking-wide
        ${styles[variant]} ${className}
      `}
    >
      {children}
    </span>
  );
}
