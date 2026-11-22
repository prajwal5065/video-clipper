import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

const styles = {
  info: ["border-accent/30 bg-accent/10", Info, "text-accent"],
  warn: ["border-warn/30 bg-warn/10", AlertTriangle, "text-warn"],
  error: ["border-bad/30 bg-bad/10", XCircle, "text-bad"],
  success: ["border-ok/30 bg-ok/10", CheckCircle2, "text-ok"],
} as const;

export function Alert({ tone = "info", title, children, className }: {
  tone?: keyof typeof styles; title?: string; children?: ReactNode; className?: string;
}) {
  const [box, Icon, icon] = styles[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex gap-3 rounded-xl border p-3.5 text-sm", box, className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", icon)} aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn("text-muted", title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  );
}
