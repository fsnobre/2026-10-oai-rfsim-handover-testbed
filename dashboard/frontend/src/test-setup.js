import "@testing-library/jest-dom/vitest";

// Recharts' ResponsiveContainer observes its container on mount, but jsdom does not
// implement ResizeObserver. Charts render at zero size under test, which is fine — the
// tests assert on surrounding content, not on chart geometry.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
