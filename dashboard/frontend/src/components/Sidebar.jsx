import { useState } from "react";
import StatusDot from "./StatusDot";

function cardIndicator(items) {
  if (!items?.length) return "red";
  if (items.every((item) => item.indicator === "green" || item.indicator === "orange")) return "green";
  if (items.some((item) => item.indicator === "orange")) return "orange";
  return "red";
}

// Roles come from the backend topology registry. Grouping is derived rather than
// hardcoded so every topology's nodes are shown: the monolithic N2 gNBs use the "gnb"
// role, which a fixed CU/DU/UE list rendered nowhere at all.
const ROLE_GROUPS = { core: "CN5G", external: "CN5G", cu: "CU", du: "DU", gnb: "gNB", ue: "UE" };
const GROUP_ORDER = ["CN5G", "CU", "DU", "gNB", "UE"];

function groupContainers(containers) {
  const byTitle = new Map();
  for (const item of containers) {
    const title = ROLE_GROUPS[item.role] || item.role || "Other";
    if (!byTitle.has(title)) byTitle.set(title, []);
    byTitle.get(title).push(item);
  }
  const ordered = GROUP_ORDER.filter((title) => byTitle.has(title));
  const extra = [...byTitle.keys()].filter((title) => !GROUP_ORDER.includes(title)).sort();
  return [...ordered, ...extra].map((title) => ({ title, items: byTitle.get(title) }));
}

const RAN_GROUPS = new Set(["CU", "DU", "gNB", "UE"]);

export default function Sidebar({ containers = [], deployed = true }) {
  // With nothing deployed the RAN entries are the fallback topology's node list, not an
  // observation — listing oai-cu/oai-du0/oai-du1 as "stopped" would name a stack the
  // operator never chose. Core containers are shared by every topology, so they stay.
  const groups = groupContainers(containers).filter(
    (group) => deployed || !RAN_GROUPS.has(group.title),
  );
  const [collapsed, setCollapsed] = useState({});
  const allCollapsed = groups.every((group) => collapsed[group.title]);

  function toggleAll() {
    const nextCollapsed = !allCollapsed;
    setCollapsed(Object.fromEntries(groups.map((group) => [group.title, nextCollapsed])));
  }

  return (
    <aside className="w-80 shrink-0 bg-monitor-panel p-5">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-[0.3em] text-cyan-300">OAI RFsim</p>
        <h1 className="mt-2 text-2xl font-semibold text-white">Handover Monitor</h1>
        <button
          type="button"
          onClick={toggleAll}
          className="mt-4 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1.5 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/15"
        >
          {allCollapsed ? "Expand all" : "Collapse all"}
        </button>
      </div>
      <div className="space-y-3">
        {!deployed && (
          <div className="card p-4 text-sm text-slate-400">
            <div className="font-semibold text-white">RAN</div>
            <p className="mt-1 text-xs">
              No CU, DU, gNB or UE container exists. Nodes appear here once a topology is deployed.
            </p>
          </div>
        )}
        {groups.map((group) => (
          <div key={group.title} className="card p-4">
            <button
              type="button"
              aria-expanded={!collapsed[group.title]}
              onClick={() => setCollapsed((prev) => ({ ...prev, [group.title]: !prev[group.title] }))}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <span className="flex items-center gap-3">
                <StatusDot indicator={cardIndicator(group.items)} />
                <span>
                  <span className="block font-semibold text-white">{group.title}</span>
                  <span className="text-xs text-slate-500">{group.items.length} container{group.items.length === 1 ? "" : "s"}</span>
                </span>
              </span>
              <span className="rounded-full bg-white/[0.06] px-2 py-1 text-xs text-slate-300">
                {collapsed[group.title] ? "expand" : "collapse"}
              </span>
            </button>
            {!collapsed[group.title] && (
              <div className="mt-3 space-y-2">
                {group.items.length === 0 ? (
                  <p className="text-sm text-slate-400">No mapped container</p>
                ) : (
                  group.items.map((item) => (
                    <div key={item.name} className="flex items-center justify-between gap-3 rounded-xl bg-black/20 px-3 py-2 text-sm">
                      <span className="min-w-0 truncate font-mono text-slate-200" title={item.name}>{item.name}</span>
                      <span className="shrink-0 rounded-full bg-black/30 px-2 py-1 text-xs text-slate-300">
                        {item.health || item.status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
