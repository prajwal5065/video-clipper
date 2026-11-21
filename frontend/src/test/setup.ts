import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });

// Radix sliders measure themselves; jsdom has no layout engine.
class RO { observe() {} unobserve() {} disconnect() {} }
beforeEach(() => { vi.stubGlobal("ResizeObserver", RO); });
