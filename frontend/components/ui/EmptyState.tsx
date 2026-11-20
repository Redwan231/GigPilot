import { LucideIcon } from "lucide-react";
import Button from "./Button";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {Icon && <Icon className="h-10 w-10 text-[var(--text-muted)] mb-4" aria-hidden="true" />}
      <h3 className="text-lg font-heading font-semibold text-[var(--text)] mb-1">{title}</h3>
      {description && <p className="text-sm text-[var(--text-muted)] mb-4 max-w-sm">{description}</p>}
      {action && <Button variant="primary" onClick={action.onClick}>{action.label}</Button>}
    </div>
  );
}
