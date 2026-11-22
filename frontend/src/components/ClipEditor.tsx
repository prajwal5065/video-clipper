import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useConfig } from "../api/hooks";
import type { Clip, Job } from "../api/types";
import { humanTime } from "../lib/utils";
import { FramingPicker } from "./FramingPicker";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Card";
import { Field, RangeSlider, Select, Switch } from "./ui/Controls";
import { Progress } from "./ui/Progress";
import { Sheet } from "./ui/Sheet";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

function NumberBox({ label, value, onChange, max }: { label: string; value: number; onChange: (v: number) => void; max: number }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted">{label}</span>
      <input
        type="number" min={0} max={max} step={0.5} value={Number.isFinite(value) ? value : ""}
        onChange={(e) => { const n = parseFloat(e.target.value); if (Number.isFinite(n)) onChange(n); }}
        className="h-10 w-full rounded-xl border border-line bg-surface-2 px-3 text-sm tabular-nums focus:border-accent/60 focus:outline-none"
      />
    </label>
  );
}

export function ClipEditor({ job, clip, onClose }: { job: Job; clip: Clip; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const limit = job.duration ?? clip.end + 120;

  const [range, setRange] = useState<[number, number]>([clip.start, clip.end]);
  const [crop, setCrop] = useState(clip.crop);
  const [style, setStyle] = useState(clip.style);
  const [captions, setCaptions] = useState(clip.captions);
  const [text, setText] = useState<string | null>(null); // null = not touched
  const [start, end] = range;

  const caption = useQuery({ queryKey: ["caption", job.id, clip.id, clip.rev], queryFn: () => api.captionText(job.id, clip.id) });
  const baseText = caption.data?.text ?? "";
  const shownText = text ?? baseText;
  const wordCount = shownText.trim() ? shownText.trim().split(/\s+/).length : 0;

  const length = end - start;
  const lengthError = length < 3 || length > 180 ? "A clip must be between 3 and 180 seconds long." : null;
  const trimChanged = start !== clip.start || end !== clip.end;
  const textChanged = captions && !!caption.data && shownText.trim() !== baseText.trim();
  let textError: string | null = null;
  if (textChanged && trimChanged) textError = "Save the new start and end first, then fix the captions.";
  else if (textChanged && caption.data && wordCount !== caption.data.count) {
    textError = `Keep the same number of words: the clip has ${caption.data.count}, you wrote ${wordCount}.`;
  }
  const problem = lengthError ?? textError;

  const startedFinal = useRef<number | null>(null);
  const edit = useMutation({
    mutationFn: (mode: "preview" | "final") =>
      api.editClip(job.id, clip.id, { mode, start, end, crop, style, captions, text: textChanged ? shownText : undefined }),
    onMutate: (mode) => { startedFinal.current = mode === "final" ? clip.rev : null; },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", job.id] }),
  });
  const rendering = clip.edit?.state === "rendering" || edit.isPending;

  // after a final save finishes, the clip has a new revision: close the panel
  useEffect(() => {
    if (startedFinal.current !== null && clip.rev > startedFinal.current && clip.edit?.state === "idle") {
      startedFinal.current = null;
      onClose();
    }
  }, [clip.rev, clip.edit?.state, onClose]);

  const dStart = useDebounced(start, 350), dEnd = useDebounced(end, 350);

  return (
    <Sheet
      open onOpenChange={(o) => !o && onClose()} title="Edit clip" description={clip.title}
      footer={
        <div className="space-y-3">
          {rendering && (
            <div aria-live="polite">
              <p className="mb-1.5 text-sm text-muted">{clip.edit?.kind === "final" || startedFinal.current !== null ? "Saving the clip..." : "Making a preview..."}</p>
              <Progress value={clip.edit?.progress ?? 0} label="Render progress" className="h-1.5" />
            </div>
          )}
          {problem && <p className="text-sm text-bad" role="alert">{problem}</p>}
          <div className="flex flex-wrap justify-end gap-3">
            <Button variant="secondary" disabled={!!problem || rendering} onClick={() => edit.mutate("preview")}>
              <Eye className="size-4" aria-hidden /> Preview (fast)
            </Button>
            <Button variant="primary" disabled={!!problem || rendering} onClick={() => edit.mutate("final")}>
              <Save className="size-4" aria-hidden /> Save changes
            </Button>
          </div>
        </div>
      }
    >
      <div className="mx-auto w-full max-w-[260px]">
        <div className="relative aspect-[9/16] overflow-hidden rounded-xl bg-black">
          {clip.preview ? (
            <video key={clip.preview.rev} controls playsInline className="h-full w-full object-contain" aria-label="Preview of your edit"
                   src={api.previewUrl(job.id, clip.id, clip.preview.rev)} />
          ) : (
            <video key={clip.rev} controls playsInline preload="metadata" className="h-full w-full object-contain" aria-label="Current clip"
                   src={api.videoUrl(job.id, clip.id, clip.rev)} />
          )}
        </div>
        <div className="mt-2 text-center">
          {clip.preview ? <Badge tone="warn">Preview, not saved yet</Badge> : <Badge>Current clip</Badge>}
        </div>
      </div>

      {clip.edit?.state === "error" && <Alert tone="error" title="The last render failed">{clip.edit.error}</Alert>}
      {edit.isError && <Alert tone="error" title="Could not start">{edit.error.message}</Alert>}

      <section aria-label="Trim">
        <h3 className="mb-3 text-sm font-semibold">Trim</h3>
        <RangeSlider labels={["Clip start", "Clip end"]} min={0} max={Math.max(1, Math.floor(limit))} step={0.5} value={[Math.min(start, limit), Math.min(end, limit)]} onChange={setRange} />
        <div className="mt-4 grid grid-cols-2 gap-3">
          <figure>
            <img alt="Frame at the start" src={api.frameUrl(job.id, dStart)} className="aspect-video w-full rounded-lg bg-surface-2 object-cover" />
            <figcaption className="mt-1 text-center text-xs text-muted">Start · {humanTime(start)}</figcaption>
          </figure>
          <figure>
            <img alt="Frame at the end" src={api.frameUrl(job.id, dEnd)} className="aspect-video w-full rounded-lg bg-surface-2 object-cover" />
            <figcaption className="mt-1 text-center text-xs text-muted">End · {humanTime(end)}</figcaption>
          </figure>
        </div>
        <div className="mt-4 grid grid-cols-3 items-end gap-3">
          <NumberBox label="Start (seconds)" value={start} max={limit} onChange={(v) => setRange([v, end])} />
          <NumberBox label="End (seconds)" value={end} max={limit} onChange={(v) => setRange([start, v])} />
          <p className={`pb-2.5 text-sm tabular-nums ${lengthError ? "text-bad" : "text-muted"}`}>{length.toFixed(1)} s long</p>
        </div>
      </section>

      <section aria-label="Look" className="space-y-5">
        <h3 className="text-sm font-semibold">Look</h3>
        {config ? (
          <>
            <Field label="Framing">
              <FramingPicker value={crop} options={config.framing} onChange={setCrop} />
            </Field>
            <div className="grid items-end gap-4 sm:grid-cols-2">
              <div className="flex items-center justify-between gap-4 rounded-xl border border-line bg-surface-2/50 px-4 py-3">
                <span className="text-sm font-medium">Captions</span>
                <Switch label="Captions" checked={captions} onCheckedChange={setCaptions} />
              </div>
              <Field label="Caption style" htmlFor="edit-style">
                <Select id="edit-style" value={style} disabled={!captions} onChange={(e) => setStyle(e.target.value)}>
                  {config.caption_styles.map((c) => <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</option>)}
                </Select>
              </Field>
            </div>
          </>
        ) : <p className="text-sm text-muted">Loading...</p>}
      </section>

      <section aria-label="Caption words">
        <h3 className="mb-1 text-sm font-semibold">Caption text</h3>
        <p className="mb-2 text-xs text-muted">Fix spelling or names. Keep the same number of words so the timing still fits.</p>
        <textarea
          aria-label="Caption text" rows={5} value={shownText} disabled={!captions || caption.isLoading}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-xl border border-line bg-surface-2 p-3 text-sm leading-relaxed focus:border-accent/60 focus:outline-none disabled:opacity-60"
        />
        {caption.data && <p className="mt-1 text-right text-xs tabular-nums text-muted">{wordCount} of {caption.data.count} words</p>}
      </section>
    </Sheet>
  );
}
