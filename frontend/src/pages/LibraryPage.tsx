import { ChevronRight, Film, Loader2, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { useJobs } from "../api/hooks";
import { Alert } from "../components/ui/Alert";
import { buttonClass } from "../components/ui/Button";
import { Badge, Card } from "../components/ui/Card";
import { timeAgo } from "../lib/utils";
import { STATUS_BADGE } from "./JobPage";

export default function LibraryPage() {
  const { data: jobs, error, isLoading } = useJobs();
  return (
    <div>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Library</h1>
          <p className="mt-2 text-muted">Everything you have clipped. It is saved on this computer.</p>
        </div>
        <Link to="/" className={buttonClass("primary")}><Plus className="size-4" aria-hidden /> New clips</Link>
      </header>

      {isLoading && <p className="text-muted" role="status">Loading...</p>}
      {error && <Alert tone="error" title="Cannot reach the server">{error.message}</Alert>}

      {jobs && jobs.length === 0 && (
        <Card className="grid place-items-center gap-3 py-16 text-center">
          <div className="grid size-12 place-items-center rounded-2xl bg-accent/10"><Film className="size-6 text-accent" aria-hidden /></div>
          <p className="font-medium">Nothing here yet</p>
          <p className="max-w-sm text-sm text-muted">Your finished clips will show up here, even after you close the page.</p>
          <Link to="/" className={buttonClass("primary", "md", "mt-2")}>Make your first clips</Link>
        </Card>
      )}

      {jobs && jobs.length > 0 && (
        <ul className="space-y-3">
          {jobs.map((j) => {
            const b = STATUS_BADGE[j.status];
            const running = j.status === "running" || j.status === "queued";
            return (
              <li key={j.id}>
                <Link to={`/jobs/${j.id}`} className="group flex items-center gap-4 rounded-2xl border border-line bg-surface p-4 transition hover:border-accent/50 sm:p-5">
                  <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-surface-2">
                    {running ? <Loader2 className="size-5 animate-spin text-accent" aria-hidden /> : <Film className="size-5 text-muted" aria-hidden />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium" title={j.label}>{j.label}</p>
                    <p className="mt-0.5 text-sm text-muted">
                      {timeAgo(j.created)}{j.status === "done" && ` · ${j.clips} clips`}{running && ` · ${Math.round(j.progress * 100)}%`}
                    </p>
                  </div>
                  <Badge tone={b.tone}>{b.label}</Badge>
                  <ChevronRight className="size-4 text-muted transition group-hover:translate-x-0.5" aria-hidden />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
