import { NavLink } from "react-router-dom";

// One tab per question an operator actually asks: what is happening right now, what did
// past experiments measure, and what can I run. gNB and UE folded into Overview; Handover
// merged into the run explorer, which reads the same artifacts.
const tabs = [
  { label: "Overview", to: "/" },
  { label: "Results", to: "/results" },
  { label: "Controls", to: "/controls" },
];

// NavLink sets aria-current="page" on the active tab automatically.
export default function NavTabs() {
  return (
    <nav className="flex gap-2 border-b border-white/10 bg-slate-950/70 px-6 py-3">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === "/"}
          className={({ isActive }) =>
            `rounded-xl px-4 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 ${
              isActive ? "bg-cyan-400/20 text-cyan-100" : "bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
