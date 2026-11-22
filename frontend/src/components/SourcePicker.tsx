import { CheckCircle2, FileVideo, FolderOpen, Link2, Loader2, UploadCloud, X } from "lucide-react";
import { useRef, useState } from "react";
import { uploadVideo } from "../api/client";
import { cn, humanSize } from "../lib/utils";
import { Alert } from "./ui/Alert";
import { TextInput } from "./ui/Controls";
import { Progress } from "./ui/Progress";

export type Source = { source_type: "link" | "path"; source: string } | null;
type Tab = "link" | "upload" | "path";

const TABS: { id: Tab; label: string; icon: typeof Link2 }[] = [
  { id: "link", label: "Paste a link", icon: Link2 },
  { id: "upload", label: "Upload a file", icon: UploadCloud },
  { id: "path", label: "Local file path", icon: FolderOpen },
];

export const isHttpLink = (v: string) => /^https?:\/\/\S+$/i.test(v.trim());

export function SourcePicker({ initial, onChange }: {
  initial?: { source_type: "link" | "path"; source: string };
  onChange: (s: Source) => void;
}) {
  const [tab, setTab] = useState<Tab>(initial?.source_type === "path" ? "path" : "link");
  const [link, setLink] = useState(initial?.source_type === "link" ? initial.source : "");
  const [path, setPath] = useState(initial?.source_type === "path" ? initial.source : "");
  const [file, setFile] = useState<{ path: string; name: string; size: number } | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // report the current source (or null while it is incomplete)
  const emit = (t: Tab, l: string, p: string, f: typeof file) => {
    if (t === "link") onChange(isHttpLink(l) ? { source_type: "link", source: l.trim() } : null);
    else if (t === "path") onChange(p.trim() ? { source_type: "path", source: p.trim().replace(/^"|"$/g, "") } : null);
    else onChange(f ? { source_type: "path", source: f.path } : null);
  };
  const pick = (t: Tab) => { setTab(t); emit(t, link, path, file); };

  async function upload(f: File) {
    setError(null); setProgress(0); setFile(null); emit("upload", link, path, null);
    try {
      const res = await uploadVideo(f, setProgress);
      setFile(res); emit("upload", link, path, res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setProgress(null);
    }
  }

  return (
    <div>
      <div role="tablist" aria-label="Where is the video?" className="mb-4 grid grid-cols-3 gap-1 rounded-xl border border-line bg-surface-2 p-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => pick(id)}
            className={cn(
              "flex h-10 items-center justify-center gap-2 rounded-lg text-sm font-medium transition",
              tab === id ? "bg-surface text-fg shadow-sm ring-1 ring-line" : "text-muted hover:text-fg",
            )}
          >
            <Icon className="size-4" aria-hidden /> <span className="hidden sm:inline">{label}</span>
            <span className="sm:hidden">{label.split(" ")[0]}</span>
          </button>
        ))}
      </div>

      {tab === "link" && (
        <div>
          <TextInput
            aria-label="Video link" type="url" inputMode="url" placeholder="https://www.youtube.com/watch?v=..."
            value={link} onChange={(e) => { setLink(e.target.value); emit("link", e.target.value, path, file); }}
          />
          {link.trim() !== "" && !isHttpLink(link) && (
            <p className="mt-2 text-xs text-bad">The link must start with http:// or https://</p>
          )}
          <p className="mt-2 text-xs text-muted">Works with YouTube and many other sites. Only use videos you own or have permission to clip.</p>
        </div>
      )}

      {tab === "upload" && (
        <div>
          <label
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) void upload(f); }}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-9 text-center transition",
              dragging ? "border-accent bg-accent/5" : "border-line hover:border-accent/50",
            )}
          >
            <input
              ref={input} data-testid="file-input" type="file" className="sr-only"
              accept="video/*,.mkv,.mov,.mp4,.webm,.m4v"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }}
            />
            {progress !== null ? <Loader2 className="size-7 animate-spin text-accent" aria-hidden /> : <UploadCloud className="size-7 text-accent" aria-hidden />}
            <p className="text-sm font-medium">{progress !== null ? "Uploading..." : "Drop a video here, or click to choose"}</p>
            <p className="text-xs text-muted">MP4, MOV, MKV, WEBM, M4V up to 4 GB</p>
          </label>
          {progress !== null && <Progress value={progress} className="mt-3" label="Upload progress" />}
          {file && (
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-ok/30 bg-ok/10 p-3 text-sm">
              <FileVideo className="size-5 shrink-0 text-ok" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{file.name}</p>
                <p className="text-xs text-muted">{humanSize(file.size)} uploaded</p>
              </div>
              <CheckCircle2 className="size-4 text-ok" aria-hidden />
              <button type="button" aria-label="Remove file" className="text-muted hover:text-fg" onClick={() => { setFile(null); emit("upload", link, path, null); }}>
                <X className="size-4" />
              </button>
            </div>
          )}
          {error && <Alert tone="error" className="mt-3">{error}</Alert>}
        </div>
      )}

      {tab === "path" && (
        <div>
          <TextInput
            aria-label="Local file path" placeholder="C:\Users\you\Videos\interview.mp4"
            value={path} onChange={(e) => { setPath(e.target.value); emit("path", link, e.target.value, file); }}
          />
          <p className="mt-2 text-xs text-muted">Best for very large videos: nothing is copied, the file is read where it is.</p>
        </div>
      )}
    </div>
  );
}
