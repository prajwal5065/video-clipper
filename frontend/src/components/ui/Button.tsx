import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-gradient-to-r from-accent to-accent-2 text-white shadow-lg shadow-accent/25 hover:brightness-110 active:brightness-95",
  secondary: "bg-surface-2 border border-line text-fg hover:border-accent/60",
  ghost: "text-muted hover:text-fg hover:bg-surface-2",
  danger: "bg-bad/10 text-bad border border-bad/30 hover:bg-bad/20",
};
const sizes: Record<Size, string> = { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-base" };

/** Same look as a Button, for <a> and <Link>. */
export function buttonClass(variant: Variant = "secondary", size: Size = "md", extra?: string) {
  return cn("inline-flex items-center justify-center gap-2 rounded-xl font-medium transition select-none",
    variants[variant], sizes[size], extra);
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export function Button({ variant = "secondary", size = "md", loading, disabled, className, children, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition select-none",
        "disabled:opacity-50 disabled:pointer-events-none",
        variants[variant], sizes[size], className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}
