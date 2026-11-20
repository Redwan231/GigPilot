"use client";
import { forwardRef, InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  srLabel?: boolean;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, srLabel, id, className = "", ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label
            htmlFor={inputId}
            className={`text-sm font-medium text-[var(--text)] ${srLabel ? "sr-only" : ""}`}
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            bg-[var(--surface)] border rounded-sm px-3 py-2 text-[var(--text)] text-sm
            placeholder:text-[var(--text-muted)]
            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--ring)]
            disabled:bg-[var(--surface-2)] disabled:opacity-60
            ${error ? "border-danger" : "border-[var(--border)]"}
            ${className}
          `}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="text-sm text-danger">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
export default Input;
