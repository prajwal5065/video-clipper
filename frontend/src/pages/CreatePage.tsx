import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Wand2 } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useConfig } from "../api/hooks";
import type { Config, Crop, JobSpec, Quality } from "../api/types";
import { FramingPicker } from "../components/FramingPicker";
import { SourcePicker, type Source } from "../components/SourcePicker";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Badge, Card, SectionTitle } from "../components/ui/Card";
import { Field, RangeSlider, Segmented, Select, Slider, Switch } from "../components/ui/Controls";

export interface Settings {
  clips: number; minLen: number; maxLen: number; crop: Crop; quality: Quality; captions: boolean; style: string;
  whisper: string; device: "auto" | "cpu" | "cuda"; computeType: "int8" | "float16"; model: string;
}
const KEY = "vc.settings";

/** Defaults from the server, then what the user used last time, then (when retrying) the old job's settings. */
export function initialSettings(config: Config, retry?: JobSpec): Settings {
  const d = config.defaults;
  let saved: Partial<Settings> = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { /* ignore */ }
  const pick = <T extends string>(v: unknown, allowed: string[], fallback: T): T =>
    (typeof v === "string" && allowed.includes(v) ? v : fallback) as T;
  const base: Settings = {
    clips: d.clips, minLen: d.min_len, maxLen: d.max_len, crop: d.crop, quality: d.quality, captions: d.captions,
    style: d.style, whisper: d.whisper, device: d.device, computeType: d.compute_type, model: d.gemini_model,
  };
  const from: Partial<Settings> = retry
    ? { clips: retry.clips, minLen: retry.min_len, maxLen: retry.max_len, crop: retry.crop, quality: retry.quality,
        captions: retry.captions, style: retry.style, whisper: retry.whisper, device: retry.device,
        computeType: retry.compute_type, model: retry.model ?? d.gemini_model }
    : saved;
  return {
    clips: typeof from.clips === "number" ? Math.min(20, Math.max(1, from.clips)) : base.clips,
    minLen: typeof from.minLen === "number" ? from.minLen : base.minLen,
    maxLen: typeof from.maxLen === "number" ? from.maxLen : base.maxLen,
    crop: pick(from.crop, config.framing.map((f) => f.id), base.crop),
    quality: pick(from.quality, config.quality.map((q) => q.id), base.quality),
    captions: typeof from.captions === "boolean" ? from.captions : base.captions,
    style: pick(from.style, config.caption_styles, base.style),
    whisper: pick(from.whisper, config.whisper_models, base.whisper),
    device: pick(from.device, ["auto", "cpu", "cuda"], base.device),
    computeType: pick(from.computeType, ["int8", "float16"], base.computeType),
    model: pick(from.model, config.gemini_models, base.model),
  };
}

function CreateForm({ config, retry }: { config: Config; retry?: JobSpec }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [source, setSource] = useState<Source>(retry ? { source_type: retry.source_type, source: retry.source } : null);
  const [s, setS] = useState<Settings>(() => initialSettings(config, retry));
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS((p) => ({ ...p, [k]: v }));

  const create = useMutation({
    mutationFn: api.createJob,
    onSuccess: (job) => { void qc.invalidateQueries({ queryKey: ["jobs"] }); navigate(`/jobs/${job.id}`); },
  });

  const framing = config.framing.find((f) => f.id === s.crop);
  const quality = config.quality.find((q) => q.id === s.quality);
  const canGenerate = !!source && config.gemini_key_set && !create.isPending;

  function submit() {
    if (!source) return;
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode */ }
    create.mutate({
      source_type: source.source_type, source: source.source, clips: s.clips, min_len: s.minLen, max_len: s.maxLen,
      whisper: s.whisper, device: s.device, compute_type: s.computeType, crop: s.crop, quality: s.quality,
      captions: s.captions, style: s.style, model: s.model || null,
    });
  }

  return (
    <div className="space-y-6">
      {!config.gemini_key_set && (
        <Alert tone="warn" title="Gemini API key not found">
          Add <code className="rounded bg-surface-2 px-1">GEMINI_API_KEY=...</code> to the <code className="rounded bg-surface-2 px-1">.env</code> file
          and restart the server. It is needed to pick the best moments.
        </Alert>
      )}

      <Card>
        <SectionTitle title="1. Choose a video" hint="Paste a link, upload a file, or point to one on this computer." />
        <SourcePicker initial={retry && { source_type: retry.source_type, source: retry.source }} onChange={setSource} />
      </Card>

      <Card>
        <SectionTitle title="2. Clips" />
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="How many clips" right={s.clips}>
            <Slider label="Number of clips" min={1} max={20} value={s.clips} onChange={(v) => set("clips", v)} />
          </Field>
          <Field label="Length of each clip" right={`${s.minLen}–${s.maxLen} s`}>
            <RangeSlider
              labels={["Shortest clip", "Longest clip"]} min={10} max={120} step={5}
              value={[Math.max(10, s.minLen), Math.min(120, s.maxLen)]}
              onChange={([a, b]) => setS((p) => ({ ...p, minLen: a, maxLen: b }))}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <SectionTitle title="3. Look" hint="How the picture fits the vertical screen, the quality, and the captions." />
        <div className="space-y-6">
          <Field label="Framing" hint={framing?.description}>
            <FramingPicker value={s.crop} options={config.framing} onChange={(v) => set("crop", v)} />
          </Field>
          <Field label="Quality" hint={quality?.description}>
            <Segmented
              label="Quality" value={s.quality} onChange={(v) => set("quality", v)}
              options={config.quality.map((q) => ({ id: q.id as Quality, label: q.label }))}
            />
          </Field>
          <div className="grid items-end gap-4 sm:grid-cols-2">
            <div className="flex items-center justify-between gap-4 rounded-xl border border-line bg-surface-2/50 px-4 py-3">
              <div>
                <p className="text-sm font-medium">Burn in captions</p>
                <p className="text-xs text-muted">Word-by-word subtitles</p>
              </div>
              <Switch label="Burn in captions" checked={s.captions} onCheckedChange={(v) => set("captions", v)} />
            </div>
            <Field label="Caption style" htmlFor="caption-style">
              <Select id="caption-style" value={s.style} disabled={!s.captions} onChange={(e) => set("style", e.target.value)}>
                {config.caption_styles.map((c) => <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</option>)}
              </Select>
            </Field>
          </div>
        </div>
      </Card>

      <Card className="!p-0">
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 sm:px-6">
            <span>
              <span className="block text-base font-semibold">Advanced</span>
              <span className="text-sm text-muted">Speech model, AI model, hardware</span>
            </span>
            <ChevronDown className="size-4 text-muted transition group-open:rotate-180" aria-hidden />
          </summary>
          <div className="grid gap-5 border-t border-line px-5 py-5 sm:grid-cols-2 sm:px-6">
            <Field label="Speech model (Whisper)" htmlFor="whisper" hint="Smaller is faster and uses less memory; larger is more accurate.">
              <Select id="whisper" value={s.whisper} onChange={(e) => set("whisper", e.target.value)}>
                {config.whisper_models.map((m) => <option key={m}>{m}</option>)}
              </Select>
            </Field>
            <Field label="AI model (Gemini)" htmlFor="model" hint="Used to choose the best moments.">
              <Select id="model" value={s.model} onChange={(e) => set("model", e.target.value)}>
                {config.gemini_models.map((m) => <option key={m}>{m}</option>)}
              </Select>
            </Field>
            <Field label="Processor" htmlFor="device">
              <Select id="device" value={s.device} onChange={(e) => set("device", e.target.value as Settings["device"])}>
                <option value="auto">Automatic</option><option value="cpu">CPU</option><option value="cuda">NVIDIA GPU</option>
              </Select>
            </Field>
            <Field label="Precision" htmlFor="compute" hint="int8 for CPU, float16 for an NVIDIA GPU.">
              <Select id="compute" value={s.computeType} onChange={(e) => set("computeType", e.target.value as Settings["computeType"])}>
                <option value="int8">int8</option><option value="float16">float16</option>
              </Select>
            </Field>
          </div>
        </details>
      </Card>

      {create.isError && <Alert tone="error" title="Could not start">{create.error.message}</Alert>}

      <Card className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <Badge tone="accent">{s.clips} clips</Badge>
          <Badge>{s.minLen}–{s.maxLen} s</Badge>
          <Badge>{framing?.label}</Badge>
          <Badge>{quality?.label}</Badge>
        </div>
        <Button variant="primary" size="lg" disabled={!canGenerate} loading={create.isPending} onClick={submit}>
          <Wand2 className="size-4" aria-hidden /> Generate clips
        </Button>
      </Card>
      {!source && <p className="-mt-3 text-center text-xs text-muted">Choose a video above to continue.</p>}
    </div>
  );
}

export default function CreatePage() {
  const { data: config, error, isLoading } = useConfig();
  const retry = (useLocation().state as { spec?: JobSpec } | null)?.spec;
  return (
    <div>
      <header className="mb-8">
        <h1 className="text-3xl font-semibold sm:text-4xl">Turn long videos into Shorts</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Paste a video and get vertical, captioned clips of its best moments, ready to preview, edit and publish.
        </p>
      </header>
      {isLoading && <p className="text-muted" role="status">Loading...</p>}
      {error && <Alert tone="error" title="Cannot reach the server">{error.message}</Alert>}
      {config && <CreateForm config={config} retry={retry} />}
    </div>
  );
}
