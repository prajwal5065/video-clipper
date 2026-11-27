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

const DAY = 86_400_000;

/** Upload every clip now, each one published at its own time (for example one a day).
 *  Each clip can go to its own YouTube account; a signed-in account is remembered, so you only sign in once. */
export function ScheduleAllDialog({ job, clips, onClose }: { job: Job; clips: Clip[]; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const accounts = config?.accounts ?? [];
  const [account, setAccount] = useState("");
  const [assign, setAssign] = useState<Record<string, string>>({}); // clip id -> account (clips not listed use the default)
  const [splitN, setSplitN] = useState(Math.ceil(clips.length / 2));
  const [restAccount, setRestAccount] = useState("");
  const [first, setFirst] = useState(() => localInputValue(24 * 60));
  const [gap, setGap] = useState(1);

  const acc = account || accounts[0]?.name;
  const rest = restAccount || accounts.find((a) => a.name !== acc)?.name || acc;
  const accOf = (c: Clip) => assign[c.id] ?? acc ?? "";
  const label = (a: { name: string; signed_in: boolean }) => `${a.name}${a.signed_in ? "" : " (sign in on first upload)"}`;

  // Each account has its own schedule: its first clip goes out at the chosen time, the next one gap days later, ...
  const used: Record<string, number> = {};
  const slots = clips.map((c) => {
    const a = accOf(c);
    const k = used[a] ?? 0;
    used[a] = k + 1;
    return new Date(new Date(first).getTime() + k * gap * DAY);
  });
  const usedNames = Object.keys(used);
  const needSignIn = accounts.filter((a) => !a.signed_in && usedNames.includes(a.name)).map((a) => a.name);
  const error = !isFutureEnough(first) ? "The first time must be at least 10 minutes from now." : null;

  const applySplit = () => {
    const n = Math.min(clips.length, Math.max(0, splitN));
    setAssign(Object.fromEntries(clips.map((c, i) => [c.id, i < n ? (acc ?? "") : (rest ?? "")])));
  };

  const run = useMutation({
    mutationFn: async () => {
      const out: { id: string; error?: string }[] = [];
      for (let i = 0; i < clips.length; i++) {
        try {
          await api.uploadClip(job.id, clips[i].id, { account: accOf(clips[i]), publish_at: slots[i].toISOString() });
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
      <Field label="YouTube account" htmlFor="sa-account" hint={accounts.length > 1 ? "Used for every clip unless you change a clip's account below." : undefined}>
        <Select id="sa-account" value={acc ?? ""} onChange={(e) => { setAccount(e.target.value); setAssign({}); }}>
          {accounts.map((a) => <option key={a.name} value={a.name}>{label(a)}</option>)}
        </Select>
      </Field>

      {accounts.length > 1 && (
        <div className="rounded-xl border border-line p-4">
          <p className="mb-3 text-sm font-medium">Split between accounts</p>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="First clips" htmlFor="sa-split-n" hint={`use ${acc}`}>
              <TextInput id="sa-split-n" type="number" min={0} max={clips.length} className="w-24" value={splitN}
                onChange={(e) => setSplitN(Math.min(clips.length, Math.max(0, Number(e.target.value) || 0)))} />
            </Field>
            <Field label="The rest go to" htmlFor="sa-rest">
              <Select id="sa-rest" className="w-48" value={rest ?? ""} onChange={(e) => setRestAccount(e.target.value)}>
                {accounts.map((a) => <option key={a.name} value={a.name}>{label(a)}</option>)}
              </Select>
            </Field>
            <Button variant="secondary" onClick={applySplit}>Apply split</Button>
          </div>
        </div>
      )}

      {needSignIn.length > 0 && (
        <Alert tone="info" title="One Google sign-in">
          A browser window opens once to sign in to {needSignIn.join(" and ")}. After that the login is remembered, so you will not be asked again.
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="First clip is published at" htmlFor="sa-first"
          hint={usedNames.length > 1 ? "Each account gets its own schedule, starting at this time." : "Your computer's time zone."}>
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
              {accounts.length > 1 && (
                <Select aria-label={`Account for ${c.title}`} className="h-9 w-32" value={accOf(c)}
                  onChange={(e) => setAssign((p) => ({ ...p, [c.id]: e.target.value }))}>
                  {accounts.map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
                </Select>
              )}
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
