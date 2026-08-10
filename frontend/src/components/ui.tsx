import type { ReactNode } from "react";

export type Tone = "neutral" | "positive" | "negative" | "accent" | "warning";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-ink",
  positive: "text-positive",
  negative: "text-negative",
  accent: "text-accent-strong",
  warning: "text-warning",
};

const BADGE_TONE: Record<Tone, string> = {
  neutral: "border-line-strong bg-surface-raised text-ink-muted",
  positive: "border-positive/40 bg-positive/10 text-positive",
  negative: "border-negative/40 bg-negative/10 text-negative",
  accent: "border-accent/40 bg-accent/10 text-accent-strong",
  warning: "border-warning/40 bg-warning/10 text-warning",
};

export function toneClass(tone: Tone): string {
  return TONE_TEXT[tone];
}

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-line bg-surface shadow-lg shadow-black/20 ${className}`}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {description && (
              <p className="mt-1 text-sm text-ink-muted">{description}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

export function Button({
  children,
  onClick,
  disabled = false,
  variant = "primary",
  size = "md",
  type = "button",
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  type?: "button" | "submit";
  title?: string;
}) {
  const sizes = {
    sm: "px-2.5 py-1 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-sm",
  }[size];
  const variants = {
    primary:
      "bg-accent text-white hover:bg-accent-strong disabled:bg-line-strong disabled:text-ink-subtle",
    secondary:
      "border border-line-strong bg-surface-raised text-ink hover:border-accent hover:text-accent-strong disabled:text-ink-subtle",
    ghost:
      "border border-transparent text-ink-muted hover:border-line-strong hover:text-ink disabled:text-ink-subtle",
  }[variant];
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed ${sizes} ${variants}`}
    >
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${BADGE_TONE[tone]}`}
    >
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface-sunken px-4 py-3">
      <dt className="text-xs font-medium text-ink-subtle">{label}</dt>
      <dd
        className={`mt-1 text-lg font-semibold tabular-nums ${TONE_TEXT[tone]}`}
      >
        {value}
      </dd>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-line bg-surface-sunken px-4 py-6 text-center text-sm text-ink-muted">
      {children}
    </p>
  );
}

/**
 * Wide tables must scroll inside their own card rather than pushing the page
 * sideways, which is what made columns collide on narrow screens.
 */
export function TableScroll({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
}: {
  children: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      scope="col"
      className={`border-b border-line px-3 py-2.5 text-xs font-semibold whitespace-nowrap text-ink-subtle uppercase ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className = "",
  colSpan,
}: {
  children: ReactNode;
  align?: "left" | "right";
  className?: string;
  colSpan?: number;
}) {
  return (
    <td
      colSpan={colSpan}
      className={`border-b border-line/60 px-3 py-2.5 align-middle ${
        align === "right" ? "text-right" : "text-left"
      } ${className}`}
    >
      {children}
    </td>
  );
}

/**
 * A checkable chip. The input stays in the layout as `sr-only` instead of being
 * absolutely positioned, which is what previously stacked every hidden control
 * in the page's top-left corner on top of the real content.
 */
export function ChipOption({
  id,
  name,
  type,
  checked,
  disabled = false,
  label,
  onChange,
}: {
  id: string;
  name?: string;
  type: "radio" | "checkbox";
  checked: boolean;
  disabled?: boolean;
  label: string;
  onChange: () => void;
}) {
  return (
    <span className="inline-flex">
      <input
        className="peer sr-only"
        type={type}
        id={id}
        name={name}
        checked={checked}
        disabled={disabled}
        onChange={onChange}
      />
      <label
        htmlFor={id}
        className="cursor-pointer rounded-full border border-line-strong bg-surface-raised px-3 py-1.5 text-sm text-ink-muted transition-colors select-none hover:border-accent/60 peer-checked:border-accent peer-checked:bg-accent/15 peer-checked:text-ink peer-disabled:cursor-not-allowed peer-disabled:opacity-50 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent"
      >
        {label}
      </label>
    </span>
  );
}

export function Fieldset({
  legend,
  children,
}: {
  legend: string;
  children: ReactNode;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2 text-xs font-semibold text-ink-subtle uppercase">
        {legend}
      </legend>
      <div className="flex flex-wrap gap-2">{children}</div>
    </fieldset>
  );
}
