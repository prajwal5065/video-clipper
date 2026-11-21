import * as SliderPrimitive from "@radix-ui/react-slider";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { ChevronDown } from "lucide-react";
import type { ReactNode, SelectHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function Field({ label, hint, children, htmlFor, right }: {
  label: string; hint?: string; children: ReactNode; htmlFor?: string; right?: ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <label htmlFor={htmlFor} className="text-sm font-medium">{label}</label>
        {right && <span className="text-sm font-medium tabular-nums text-accent">{right}</span>}
      </div>
      {children}
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function TextInput({ className, ...rest }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cn(
        "h-11 w-full rounded-xl border border-line bg-surface-2 px-3.5 text-sm placeholder:text-muted/70",
        "transition focus:border-accent/60 focus:outline-none", className,
      )}
    />
  );
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        {...rest}
        className={cn(
          "h-11 w-full appearance-none rounded-xl border border-line bg-surface-2 px-3.5 pr-9 text-sm",
          "transition focus:border-accent/60 focus:outline-none", className,
        )}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: { id: T; label: string }[]; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid auto-cols-fr grid-flow-col gap-1 rounded-xl border border-line bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.id} type="button" role="radio" aria-checked={value === o.id} onClick={() => onChange(o.id)}
          className={cn(
            "h-9 rounded-lg px-3 text-sm font-medium transition",
            value === o.id ? "bg-surface text-fg shadow-sm ring-1 ring-line" : "text-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Switch({ checked, onCheckedChange, label }: { checked: boolean; onCheckedChange: (v: boolean) => void; label: string }) {
  return (
    <SwitchPrimitive.Root
      checked={checked} onCheckedChange={onCheckedChange} aria-label={label}
      className="relative h-6 w-11 shrink-0 rounded-full border border-line bg-surface-2 transition data-[state=checked]:border-transparent data-[state=checked]:bg-accent"
    >
      <SwitchPrimitive.Thumb className="block size-4.5 translate-x-0.5 rounded-full bg-fg shadow transition-transform data-[state=checked]:translate-x-5.5 data-[state=checked]:bg-white" />
    </SwitchPrimitive.Root>
  );
}

const thumb = "block size-5 rounded-full border-2 border-accent bg-surface shadow transition hover:scale-110 focus-visible:outline-2";

export function Slider({ value, onChange, min, max, step = 1, label }: {
  value: number; onChange: (v: number) => void; min: number; max: number; step?: number; label: string;
}) {
  return (
    <SliderPrimitive.Root
      value={[value]} onValueChange={([v]) => onChange(v)} min={min} max={max} step={step}
      className="relative flex h-6 w-full touch-none select-none items-center"
    >
      <SliderPrimitive.Track className="relative h-1.5 grow rounded-full bg-surface-2 ring-1 ring-line">
        <SliderPrimitive.Range className="absolute h-full rounded-full bg-gradient-to-r from-accent to-accent-2" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb aria-label={label} className={thumb} />
    </SliderPrimitive.Root>
  );
}

export function RangeSlider({ value, onChange, min, max, step = 1, labels }: {
  value: [number, number]; onChange: (v: [number, number]) => void; min: number; max: number; step?: number;
  labels: [string, string];
}) {
  return (
    <SliderPrimitive.Root
      value={value} onValueChange={(v) => onChange([v[0], v[1]])} min={min} max={max} step={step} minStepsBetweenThumbs={1}
      className="relative flex h-6 w-full touch-none select-none items-center"
    >
      <SliderPrimitive.Track className="relative h-1.5 grow rounded-full bg-surface-2 ring-1 ring-line">
        <SliderPrimitive.Range className="absolute h-full rounded-full bg-gradient-to-r from-accent to-accent-2" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb aria-label={labels[0]} className={thumb} />
      <SliderPrimitive.Thumb aria-label={labels[1]} className={thumb} />
    </SliderPrimitive.Root>
  );
}
