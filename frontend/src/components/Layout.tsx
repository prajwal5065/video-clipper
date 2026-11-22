import { Library, Moon, Play, Settings, Sparkles, Sun } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../api/hooks";
import { cn } from "../lib/utils";

const NAV = [
  { to: "/", label: "New clips", icon: Sparkles, end: true },
  { to: "/library", label: "Library", icon: Library, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-accent to-accent-2 shadow-lg shadow-accent/30">
        <Play className="size-4 translate-x-px fill-white text-white" aria-hidden />
      </div>
      <span className="text-[15px] font-semibold tracking-tight">Video Clipper</span>
    </div>
  );
}

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button" onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="grid size-9 place-items-center rounded-xl text-muted transition hover:bg-surface-2 hover:text-fg"
    >
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

export function Layout() {
  return (
    <div className="min-h-screen">
      {/* desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-line bg-surface/60 px-4 py-5 backdrop-blur md:flex">
        <Brand />
        <nav className="mt-8 flex flex-col gap-1" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) => cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                isActive ? "bg-accent/10 text-accent" : "text-muted hover:bg-surface-2 hover:text-fg",
              )}
            >
              <Icon className="size-4" aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex items-center justify-between text-xs text-muted">
          <span>Runs on this computer</span>
          <ThemeToggle />
        </div>
      </aside>

      {/* mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-bg/80 px-4 py-3 backdrop-blur md:hidden">
        <Brand />
        <ThemeToggle />
      </header>

      <main className="mx-auto w-full max-w-5xl px-4 pb-28 pt-6 sm:px-6 md:ml-60 md:max-w-none md:px-10 md:pb-16 md:pt-10">
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>

      {/* mobile bottom navigation */}
      <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-3 border-t border-line bg-bg/90 backdrop-blur md:hidden" aria-label="Main (mobile)">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to} to={to} end={end}
            className={({ isActive }) => cn("flex flex-col items-center gap-1 py-2.5 text-xs font-medium", isActive ? "text-accent" : "text-muted")}
          >
            <Icon className="size-5" aria-hidden /> {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
