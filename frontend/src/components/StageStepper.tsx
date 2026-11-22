import { AudioLines, CheckCircle2, Download, Film, Loader2, Sparkles, XCircle } from "lucide-react";
import type { Job, Stage } from "../api/types";
import { cn, isActive } from "../lib/utils";

const STAGES: { id: Stage; label: string; icon: typeof Download }[] = [
  { id: "download", label: "Get the video", icon: Download },
  { id: "transcribe", label: "Transcribe", icon: AudioLines },
  { id: "select", label: "Find the best moments", icon: Sparkles },
  { id: "render", label: "Render the clips", icon: Film },
];
const ORDER: Stage[] = ["download", "transcribe", "select", "render", "done"];

type State = "done" | "active" | "failed" | "pending";

export function stageStates(job: Pick<Job, "status" | "stage">): State[] {
  if (job.status === "done") return STAGES.map(() => "done");
  const cur = ORDER.indexOf(job.stage); // -1 while queued
  return STAGES.map((_, i) => {
    if (i < cur) return "done";
    if (i === cur) return isActive(job.status) ? "active" : "failed";
    return "pending";
  });
}

export function StageStepper({ job }: { job: Job }) {
  const states = stageStates(job);
  return (
    <ol className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Progress by step">
      {STAGES.map((s, i) => {
        const st = states[i];
        const sub = s.id === "download" && job.spec.source_type === "path" && st === "done" ? "Local file"
          : { done: "Done", active: "In progress", failed: job.status === "failed" ? "Failed" : "Stopped", pending: "Waiting" }[st];
        return (
          <li
            key={s.id} aria-current={st === "active" ? "step" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-xl border p-3 transition",
              st === "active" ? "border-accent/50 bg-accent/5" : "border-line bg-surface-2/40",
              st === "failed" && "border-bad/40 bg-bad/5",
            )}
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface">
              {st === "done" ? <CheckCircle2 className="size-4 text-ok" aria-hidden />
                : st === "active" ? <Loader2 className="size-4 animate-spin text-accent" aria-hidden />
                : st === "failed" ? <XCircle className="size-4 text-bad" aria-hidden />
                : <s.icon className={cn("size-4", "text-muted")} aria-hidden />}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{s.label}</span>
              <span className={cn("block text-xs", st === "pending" ? "text-muted/70" : "text-muted")}>{sub}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
