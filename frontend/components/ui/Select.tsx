"use client";
import { forwardRef, SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  srLabel?: boolean;
  options: { value: string; label: string }[];
  placeholder?: string;
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, srLabel, id, options, placeholder, className = "", ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className={`text-sm font-medium text-[var(--text)] ${srLabel ? "sr-only" : ""}`}>
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={inputId}
          className={`
            bg-[var(--surface)] border rounded-sm px-3 py-2 text-[var(--text)] text-sm
            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--ring)]
            disabled:bg-[var(--surface-2)] disabled:opacity-60
            ${error ? "border-danger" : "border-[var(--border)]"}
            ${className}
          `}
          aria-invalid={!!error}
          {...props}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>
    );
  }
);
Select.displayName = "Select";
export default Select;
