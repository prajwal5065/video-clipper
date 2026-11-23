import { Clock, Download, ExternalLink, Loader2, Pencil, Sparkles, Upload } from "lucide-react";
import { api } from "../api/client";
import type { Clip } from "../api/types";
import { clipLength, formatWhen } from "../lib/utils";
import { Button, buttonClass } from "./ui/Button";
import { Badge, Card } from "./ui/Card";

function Status({ clip }: { clip: Clip }) {
  const yt = clip.yt;
  return (
    <>
      {clip.edit?.state === "rendering" && <Badge tone="accent"><Loader2 className="size-3 animate-spin" aria-hidden /> Updating</Badge>}
      {clip.rev > 1 && clip.edit?.state !== "rendering" && <Badge>Edited</Badge>}
      {yt?.state === "uploading" && <Badge tone="accent"><Loader2 className="size-3 animate-spin" aria-hidden /> Uploading</Badge>}
      {yt?.state === "done" && (
        <a href={yt.url ?? "#"} target="_blank" rel="noreferrer">
          <Badge tone="ok">{yt.scheduled ? `Scheduled ${formatWhen(yt.scheduled)}` : "On YouTube"} <ExternalLink className="size-3" aria-hidden /></Badge>
        </a>
      )}
      {yt?.state === "error" && <Badge tone="bad">Upload failed</Badge>}
    </>
  );
}

export function ClipCard({ jobId, clip, onEdit, onUpload }: {
  jobId: string; clip: Clip; onEdit?: () => void; onUpload?: () => void;
}) {
  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <div className="aspect-[9/16] w-full bg-black">
        <video
          key={clip.rev} controls playsInline preload="metadata" className="h-full w-full object-contain"
          src={api.videoUrl(jobId, clip.id, clip.rev)} aria-label={`Preview of ${clip.title}`}
        />
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <h3 className="line-clamp-2 text-sm font-semibold leading-snug">{clip.title}</h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {clip.score != null && <Badge tone="accent"><Sparkles className="size-3" aria-hidden /> {clip.score}</Badge>}
            <Badge><Clock className="size-3" aria-hidden /> {clipLength(clip.start, clip.end)}</Badge>
            <Status clip={clip} />
          </div>
        </div>
        {clip.reason && <p className="line-clamp-3 text-xs text-muted">{clip.reason}</p>}
        <div className="mt-auto grid grid-cols-2 gap-2">
          {onEdit && <Button size="sm" variant="secondary" onClick={onEdit}><Pencil className="size-4" aria-hidden /> Edit</Button>}
          {onUpload && <Button size="sm" variant="secondary" onClick={onUpload}><Upload className="size-4" aria-hidden /> YouTube</Button>}
          <a className={buttonClass("ghost", "sm", "col-span-2")} href={api.downloadUrl(jobId, clip.id)} download>
            <Download className="size-4" aria-hidden /> Download
          </a>
        </div>
      </div>
    </Card>
  );
}
