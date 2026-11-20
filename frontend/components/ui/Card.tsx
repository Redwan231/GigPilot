import { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  clickable?: boolean;
}

export default function Card({ clickable, className = "", children, ...props }: CardProps) {
  return (
    <div
      className={`
        bg-[var(--surface)] border border-[var(--border)] rounded-md p-4 shadow-e1
        ${clickable ? "cursor-pointer hover:border-[var(--accent)]/40 transition-colors" : ""}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}
