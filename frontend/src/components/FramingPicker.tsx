import type { Crop, Option } from "../api/types";
import { cn } from "../lib/utils";

/** A tiny phone-shaped diagram of how the picture is placed in the vertical frame. */
function Diagram({ mode }: { mode: Crop }) {
  const full = mode === "fit" || mode === "fit-black";
  return (
    <div className="relative h-16 w-9 shrink-0 overflow-hidden rounded-md border border-line bg-surface-2" aria-hidden>
      {mode === "fit" && <div className="absolute inset-0 bg-gradient-to-b from-accent/60 via-accent-2/30 to-accent/60 blur-[2px]" />}
      {mode === "fit-black" && <div className="absolute inset-0 bg-black" />}
      {full ? (
        <div className="absolute inset-x-0 top-1/2 h-5 -translate-y-1/2 bg-gradient-to-br from-accent to-accent-2" />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-accent to-accent-2">
          {mode === "face" && <div className="absolute left-1/2 top-3 size-3 -translate-x-1/2 rounded-full bg-white/90" />}
        </div>
      )}
    </div>
  );
}

export function FramingPicker({ value, options, onChange }: { value: Crop; options: Option[]; onChange: (v: Crop) => void }) {
  return (
    <div role="radiogroup" aria-label="Framing" className="grid gap-3 sm:grid-cols-2">
      {options.map((o) => {
        const on = value === o.id;
        return (
          <button
            key={o.id} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.id as Crop)}
            className={cn(
              "flex items-center gap-4 rounded-xl border p-3.5 text-left transition",
              on ? "border-accent bg-accent/5 ring-1 ring-accent/40" : "border-line bg-surface-2/50 hover:border-accent/40",
            )}
          >
            <Diagram mode={o.id as Crop} />
            <span className="min-w-0">
              <span className="block text-sm font-medium">{o.label}</span>
              <span className="mt-0.5 block text-xs leading-snug text-muted">{o.description}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
