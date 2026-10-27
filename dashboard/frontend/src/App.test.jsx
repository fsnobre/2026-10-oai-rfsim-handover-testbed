import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import App from "./App";

// The dashboard is expected to render before any backend data arrives, so every network
// call is stubbed and the WebSocket never connects.
vi.mock("./utils/api", () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiPost: vi.fn(() => Promise.resolve({})),
  getApiToken: () => "",
  setApiToken: () => {},
  wsUrl: () => "ws://localhost:8000/ws",
  API_BASE_URL: "http://localhost:8000",
}));

vi.mock("./hooks/useWebSocket", () => ({
  useWebSocket: () => ({ state: null, connection: "connecting" }),
}));

// Renders and flushes the mounted data fetches (capabilities, run list) so assertions
// run against settled state rather than racing React's effects.
async function renderAt(path) {
  const result = render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  await act(async () => {
    await Promise.resolve();
  });
  return result;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("navigation", () => {
  test("exposes exactly three top-level tabs", async () => {
    await renderAt("/");
    const nav = screen.getByRole("navigation");
    const links = nav.querySelectorAll("a");
    expect([...links].map((link) => link.textContent)).toEqual(["Overview", "Results", "Controls"]);
  });

  test("renders Overview before any state has arrived", async () => {
    await renderAt("/");
    // Falls back to the default topology label rather than crashing on a null state.
    expect(screen.getByText(/handover cockpit/i)).toBeTruthy();
  });
});

describe("legacy route redirects", () => {
  test.each([
    ["/gnb", /handover cockpit/i],
    ["/ue", /handover cockpit/i],
  ])("%s folds into Overview", async (path, expected) => {
    await renderAt(path);
    expect(screen.getByText(expected)).toBeTruthy();
  });

  test.each(["/handover", "/runs", "/results"])("%s lands on the run explorer", async (path) => {
    await renderAt(path);
    expect(screen.getByText("Experiment runs")).toBeTruthy();
  });

  test("a bookmarked run id is preserved across the redirect", async () => {
    await renderAt("/runs/20260619_145515_f1_handover_smoke");
    expect(screen.getByText("Experiment runs")).toBeTruthy();
  });

  test("campaigns redirect into the Results sub-view", async () => {
    await renderAt("/campaigns");
    expect(screen.getByText("Repeated smoke-test campaign")).toBeTruthy();
  });
});
