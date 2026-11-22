import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RotateCcw, Square, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useJob, useNow } from "../api/hooks";
import type { Job, Status } from "../api/types";
import { ClipCard } from "../components/ClipCard";
import { StageStepper } from "../components/StageStepper";
import { Alert } from "../components/ui/Alert";
import { Button, buttonClass } from "../components/ui/Button";
import { Badge, Card } from "../components/ui/Card";
import { Progress } from "../components/ui/Progress";
import { describeDownload, humanTime, isActive } from "../lib/utils";

export const STATUS_BADGE: Record<Status, { label: string; tone: "neutral" | "accent" | "ok" | "warn" | "bad" }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Working", tone: "accent" },
  done: { label: "Done", tone: "ok" },
  failed: { label: "Failed", tone: "bad" },
  cancelled: { label: "Cancelled", tone: "warn" },
  interrupted: { label: "Interrupted", tone: "warn" },
};

/** What the job is doing right now, in plain words, with a detail bar where one makes sense. */
function Activity({ job }: { job: Job }) {
  let headline = job.message;
  let detail = "";
  let bar: number | null = null;
  if (job.stage === "download" && job.download) {
    const d = describeDownload(job.download);
    headline = d.headline; detail = d.detail; bar = job.download.best;
  } else if (job.stage === "transcribe" && job.transcribe && job.transcribe.total > 0) {
    bar = job.transcribe.done / job.transcribe.total;
  } else if (job.stage === "render" && job.render) {
    headline = `Rendering clip ${job.render.index} of ${job.render.total}`;
    detail = job.render.title;
  }
  return (
    <div className="mt-5 rounded-xl border border-line bg-surface-2/50 p-4" aria-live="polite">
      <p className="text-sm font-medium">{headline}</p>
      {detail && <p className="mt-0.5 text-sm text-muted">{detail}</p>}
      {bar !== null && <Progress value={bar} className="mt-3 h-1.5" label="Current step" />}
    </div>
  );
}

export default function JobPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: job, error, isLoading } = useJob(id);
  const active = isActive(job?.status);
  const now = useNow(1000, active);

  const cancel = useMutation({
    mutationFn: () => api.cancelJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteJob(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["jobs"] }); navigate("/library"); },
  });

  if (isLoading) return <p className="text-muted" role="status">Loading...</p>;
  if (error || !job) {
    return (
      <div className="space-y-4">
        <Alert tone="error" title="Could not load this job">{error?.message ?? "Not found."}</Alert>
        <Link to="/library" className={buttonClass("secondary")}><ArrowLeft className="size-4" aria-hidden /> Back to the library</Link>
      </div>
    );
  }

  const badge = STATUS_BADGE[job.status];
  const elapsed = active ? now / 1000 - job.created : job.updated - job.created;
  const pct = Math.round(job.progress * 100);
  const stepNo = ["download", "transcribe", "select", "render"].indexOf(job.stage) + 1;
  const caption = job.status === "running" && stepNo > 0 ? `Step ${stepNo} of 4`
    : job.status === "queued" ? "Waiting to start" : badge.label;
  const confirmDelete = () => { if (window.confirm("Delete this job and its clips from your computer?")) remove.mutate(); };

  return (
    <div className="space-y-6">
      <div>
        <Link to="/library" className="inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-fg">
          <ArrowLeft className="size-4" aria-hidden /> Library
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="min-w-0 max-w-full truncate text-2xl font-semibold" title={job.label}>{job.label}</h1>
          <Badge tone={badge.tone}>{badge.label}</Badge>
        </div>
      </div>

      {job.status !== "done" && (
        <Card>
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-sm text-muted">{caption}</p>
              <p className="mt-1 text-4xl font-semibold tabular-nums" aria-label={`${pct} percent`}>{pct}%</p>
            </div>
            <div className="text-right text-sm text-muted">
              Elapsed
              <p className="font-medium tabular-nums text-fg">{humanTime(elapsed)}</p>
            </div>
          </div>
          <Progress value={job.progress} className="mt-4 h-2.5" label="Overall progress" />
          <div className="mt-6"><StageStepper job={job} /></div>
          {active && <Activity job={job} />}

          {job.status === "failed" && <Alert tone="error" title="Something went wrong" className="mt-5">{job.error ?? "Unknown error"}</Alert>}
          {job.status === "cancelled" && <Alert tone="warn" title="You cancelled this job" className="mt-5" />}
          {job.status === "interrupted" && (
            <Alert tone="warn" title="This job was interrupted" className="mt-5">
              The server was restarted while it was running. Nothing was lost, but you need to start it again.
            </Alert>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            {active && (
              <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>
                <Square className="size-4" aria-hidden /> Cancel
              </Button>
            )}
            {!active && (
              <>
                <Link to="/" state={{ spec: job.spec }} className={buttonClass("primary")}>
                  <RotateCcw className="size-4" aria-hidden /> Try again
                </Link>
                <Button variant="ghost" onClick={confirmDelete} loading={remove.isPending}>
                  <Trash2 className="size-4" aria-hidden /> Delete
                </Button>
              </>
            )}
          </div>
          {(cancel.isError || remove.isError) && (
            <Alert tone="error" className="mt-4">{(cancel.error ?? remove.error)?.message}</Alert>
          )}
        </Card>
      )}

      {job.status === "done" && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted">
              <span className="font-medium text-fg">{job.clips.length} clips</span> ready · finished in {humanTime(elapsed)}
            </p>
            <div className="flex gap-2">
              <Link to="/" state={{ spec: job.spec }} className={buttonClass("secondary", "sm")}>
                <RotateCcw className="size-4" aria-hidden /> Run again
              </Link>
              <Button size="sm" variant="ghost" onClick={confirmDelete} loading={remove.isPending}>
                <Trash2 className="size-4" aria-hidden /> Delete
              </Button>
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {job.clips.map((c) => <ClipCard key={c.id} jobId={job.id} clip={c} />)}
          </div>
        </>
      )}
    </div>
  );
}
