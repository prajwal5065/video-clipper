import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { useConfig } from "../api/hooks";
import type { Clip, Job } from "../api/types";
import { formatWhen, isFutureEnough, localInputValue } from "../lib/utils";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
import { Field, Select, TextInput } from "./ui/Controls";
import { Sheet } from "./ui/Sheet";

/** Upload every clip now, each one published at its own time (for example one a day). */
export function ScheduleAllDialog({ job, clips, onClose }: { job: Job; clips: Clip[]; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const [account, setAccount] = useState("");
  const [first, setFirst] = useState(() => localInputValue(24 * 60));
  const [gap, setGap] = useState(1);
  const acc = account || config?.accounts[0]?.name;
  const slots = clips.map((_, i) => new Date(new Date(first).getTime() + i * gap * 86_400_000));
  const error = !isFutureEnough(first) ? "The first time must be at least 10 minutes from now." : null;

  const run = useMutation({
    mutationFn: async () => {
      const out: { id: string; error?: string }[] = [];
      for (let i = 0; i < clips.length; i++) {
        try {
          await api.uploadClip(job.id, clips[i].id, { account: acc, publish_at: slots[i].toISOString() });
          out.push({ id: clips[i].id });
        } catch (e) {
          out.push({ id: clips[i].id, error: e instanceof Error ? e.message : "Failed" });
        }
      }
      return out;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", job.id] }),
  });

  return (
    <Sheet
      open onOpenChange={(o) => !o && onClose()} title="Schedule all clips"
      description={`${clips.length} clips, uploaded now and published one after another`}
      footer={
        <div className="flex items-center justify-between gap-3">
          {error ? <p className="text-sm text-bad" role="alert">{error}</p> : <span />}
          <Button variant="primary" disabled={!!error || !config?.youtube_ready || run.isSuccess} loading={run.isPending} onClick={() => run.mutate()}>
            <CalendarClock className="size-4" aria-hidden /> Upload and schedule
          </Button>
        </div>
      }
    >
      {config && !config.youtube_ready && (
        <Alert tone="warn" title="YouTube is not set up yet">Save your Google OAuth file as <code>client_secret.json</code>, then restart the server.</Alert>
      )}
      <Field label="YouTube account" htmlFor="sa-account">
        <Select id="sa-account" value={acc ?? ""} onChange={(e) => setAccount(e.target.value)}>
          {(config?.accounts ?? []).map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
        </Select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="First clip is published at" htmlFor="sa-first" hint="Your computer's time zone.">
          <TextInput id="sa-first" type="datetime-local" value={first} onChange={(e) => setFirst(e.target.value)} />
        </Field>
        <Field label="Days between clips" htmlFor="sa-gap">
          <TextInput id="sa-gap" type="number" min={1} max={30} value={gap} onChange={(e) => setGap(Math.min(30, Math.max(1, Number(e.target.value) || 1)))} />
        </Field>
      </div>
      <ul className="divide-y divide-line rounded-xl border border-line" aria-label="Schedule">
        {clips.map((c, i) => {
          const r = run.data?.find((x) => x.id === c.id);
          return (
            <li key={c.id} className="flex items-center gap-3 px-4 py-3 text-sm">
              <span className="min-w-0 flex-1 truncate">{c.title}</span>
              <span className="shrink-0 tabular-nums text-muted">{Number.isNaN(slots[i].getTime()) ? "" : formatWhen(slots[i].toISOString())}</span>
              {r && (r.error ? <XCircle className="size-4 text-bad" aria-label={r.error} /> : <CheckCircle2 className="size-4 text-ok" aria-label="Queued" />)}
            </li>
          );
        })}
      </ul>
      {run.isSuccess && (
        <Alert tone="success" title="Queued">
          The clips upload one after another. Watch each clip's status on the page. Close this panel any time.
        </Alert>
      )}
      {run.data?.some((r) => r.error) && <Alert tone="error" title="Some clips could not be queued">{run.data.find((r) => r.error)?.error}</Alert>}
    </Sheet>
  );
}
