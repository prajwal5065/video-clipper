import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ExternalLink, Loader2, Sparkles, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useConfig } from "../api/hooks";
import type { Clip, Job, MetaBody, UploadBody } from "../api/types";
import { formatWhen, isFutureEnough, localInputValue, splitList } from "../lib/utils";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
import { Field, Segmented, Select, Switch, TextInput } from "./ui/Controls";
import { Sheet } from "./ui/Sheet";

type Privacy = "private" | "unlisted" | "public";
const textarea = "w-full rounded-xl border border-line bg-surface-2 p-3 text-sm leading-relaxed focus:border-accent/60 focus:outline-none";

export function UploadDialog({ job, clip, onClose }: { job: Job; clip: Clip; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: config } = useConfig();
  const refresh = () => qc.invalidateQueries({ queryKey: ["job", job.id] });

  const [title, setTitle] = useState(clip.meta?.title ?? "");
  const [description, setDescription] = useState(clip.meta?.description ?? "");
  const [hashtags, setHashtags] = useState((clip.meta?.hashtags ?? []).join(", "));
  const [tags, setTags] = useState((clip.meta?.tags ?? []).join(", "));
  const [account, setAccount] = useState("");
  const [privacy, setPrivacy] = useState<Privacy | null>(null);
  const [kids, setKids] = useState<boolean | null>(null);
  const [when, setWhen] = useState<"now" | "later">("now");
  const [at, setAt] = useState(() => localInputValue(24 * 60));

  const fill = (m: MetaBody) => {
    setTitle(m.title); setDescription(m.description); setHashtags(m.hashtags.join(", ")); setTags(m.tags.join(", "));
  };
  // metadata written on the server (e.g. generated during an upload) shows up here
  useEffect(() => { if (clip.meta) fill(clip.meta); }, [clip.meta?.title, clip.meta?.description]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = useMutation({
    mutationFn: () => api.generateMeta(job.id, clip.id, config?.defaults.gemini_model),
    onSuccess: (m) => { fill(m); void refresh(); },
  });

  const acc = account || config?.accounts[0]?.name;
  const priv = privacy ?? config?.defaults.privacy ?? "private";
  const forKids = kids ?? config?.defaults.made_for_kids ?? false;
  const scheduleError = when === "later" && !isFutureEnough(at) ? "Pick a time at least 10 minutes from now." : null;
  const uploading = clip.yt?.state === "uploading";
  const ready = config?.youtube_ready ?? false;

  const upload = useMutation({
    mutationFn: async () => {
      if (title.trim()) {
        await api.saveMeta(job.id, clip.id, { title: title.trim(), description, hashtags: splitList(hashtags), tags: splitList(tags) });
      }
      const body: UploadBody = { account: acc, privacy: priv, made_for_kids: forKids,
        publish_at: when === "later" ? new Date(at).toISOString() : undefined };
      return api.uploadClip(job.id, clip.id, body);
    },
    onSuccess: () => { void refresh(); },
  });

  const yt = clip.yt;
  return (
    <Sheet
      open onOpenChange={(o) => !o && onClose()} title="Publish to YouTube" description={clip.title}
      footer={
        <div className="space-y-2">
          {scheduleError && <p className="text-sm text-bad" role="alert">{scheduleError}</p>}
          <div className="flex justify-end">
            <Button variant="primary" disabled={!ready || !!scheduleError || uploading} loading={upload.isPending}
                    onClick={() => upload.mutate()}>
              {when === "later" ? <CalendarClock className="size-4" aria-hidden /> : <Upload className="size-4" aria-hidden />}
              {when === "later" ? "Schedule upload" : yt?.state === "done" ? "Upload again" : "Upload now"}
            </Button>
          </div>
        </div>
      }
    >
      {!ready && (
        <Alert tone="warn" title="YouTube is not set up yet">
          Save your Google OAuth file as <code>client_secret.json</code> next to the app (see the README), then restart the server.
        </Alert>
      )}
      {uploading && (
        <Alert tone="info" title={`Uploading to ${yt?.account}...`}>
          <span className="inline-flex items-center gap-2"><Loader2 className="size-3.5 animate-spin" aria-hidden /> {yt?.message}</span>
        </Alert>
      )}
      {yt?.state === "done" && (
        <Alert tone="success" title={yt.scheduled ? `Scheduled on ${yt.account} for ${formatWhen(yt.scheduled)}` : `Uploaded to ${yt.account}`}>
          <a href={yt.url ?? "#"} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
            Open on YouTube <ExternalLink className="size-3" aria-hidden />
          </a>
        </Alert>
      )}
      {yt?.state === "error" && <Alert tone="error" title="The upload failed">{yt.error}</Alert>}
      {upload.isError && <Alert tone="error" title="Could not start the upload">{upload.error.message}</Alert>}
      {generate.isError && <Alert tone="error" title="Could not write the details">{generate.error.message}</Alert>}

      <section aria-label="Details" className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Title and description</h3>
          <Button size="sm" variant="secondary" loading={generate.isPending} onClick={() => generate.mutate()}>
            <Sparkles className="size-4" aria-hidden /> {clip.meta || title ? "Rewrite with AI" : "Write with AI"}
          </Button>
        </div>
        <Field label="Title" htmlFor="yt-title" right={<span className={title.length > 100 ? "text-bad" : "text-muted"}>{title.length}/100</span>}>
          <TextInput id="yt-title" value={title} maxLength={100} placeholder="Leave empty and AI writes it when you upload" onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Description" htmlFor="yt-desc">
          <textarea id="yt-desc" rows={5} value={description} className={textarea} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Field label="Hashtags" htmlFor="yt-hashtags" hint="Separated by commas. #Shorts is always added.">
          <TextInput id="yt-hashtags" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
        </Field>
        <Field label="Search tags" htmlFor="yt-tags" hint="Words and phrases people would search for, separated by commas.">
          <TextInput id="yt-tags" value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
      </section>

      <section aria-label="Publishing" className="space-y-4">
        <h3 className="text-sm font-semibold">Publishing</h3>
        <Field label="YouTube account" htmlFor="yt-account">
          <Select id="yt-account" value={acc ?? ""} onChange={(e) => setAccount(e.target.value)}>
            {(config?.accounts ?? []).map((a) => <option key={a.name} value={a.name}>{a.name}{a.signed_in ? "" : " (sign in on first upload)"}</option>)}
          </Select>
        </Field>
        <Field label="Visibility">
          <Segmented<Privacy> label="Visibility" value={priv} onChange={setPrivacy}
            options={[{ id: "private", label: "Private" }, { id: "unlisted", label: "Unlisted" }, { id: "public", label: "Public" }]} />
        </Field>
        <div className="flex items-center justify-between gap-4 rounded-xl border border-line bg-surface-2/50 px-4 py-3">
          <div>
            <p className="text-sm font-medium">Made for kids</p>
            <p className="text-xs text-muted">Required by YouTube. Leave off unless the video is aimed at children.</p>
          </div>
          <Switch label="Made for kids" checked={forKids} onCheckedChange={setKids} />
        </div>
        <Field label="When">
          <Segmented<"now" | "later"> label="When" value={when} onChange={setWhen}
            options={[{ id: "now", label: "Now" }, { id: "later", label: "Schedule" }]} />
        </Field>
        {when === "later" && (
          <Field label="Publish at" htmlFor="yt-at" hint="Your computer's time zone. The video is uploaded as private and published automatically at this time.">
            <TextInput id="yt-at" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
          </Field>
        )}
        <Alert tone="info">
          New Google Cloud projects may be limited to private uploads until Google verifies the app. If a public upload stays private,
          change its visibility in YouTube Studio.
        </Alert>
      </section>
    </Sheet>
  );
}
