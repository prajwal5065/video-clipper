import { Clock, Download, Sparkles } from "lucide-react";
import { api } from "../api/client";
import type { Clip } from "../api/types";
import { clipLength } from "../lib/utils";
import { Badge, Card } from "./ui/Card";
import { buttonClass } from "./ui/Button";

export function ClipCard({ jobId, clip }: { jobId: string; clip: Clip }) {
  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <div className="aspect-[9/16] w-full bg-black">
        <video
          controls playsInline preload="metadata" className="h-full w-full object-contain"
          src={api.videoUrl(jobId, clip.id, clip.rev)} aria-label={`Preview of ${clip.title}`}
        />
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <h3 className="line-clamp-2 text-sm font-semibold leading-snug">{clip.title}</h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {clip.score != null && <Badge tone="accent"><Sparkles className="size-3" aria-hidden /> {clip.score}</Badge>}
            <Badge><Clock className="size-3" aria-hidden /> {clipLength(clip.start, clip.end)}</Badge>
          </div>
        </div>
        {clip.reason && <p className="line-clamp-3 text-xs text-muted">{clip.reason}</p>}
        <a className={buttonClass("secondary", "sm", "mt-auto")} href={api.downloadUrl(jobId, clip.id)} download>
          <Download className="size-4" aria-hidden /> Download
        </a>
      </div>
    </Card>
  );
}
