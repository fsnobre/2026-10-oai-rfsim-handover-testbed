import StatusDot from "./StatusDot";

const NODE_W = 150;
const NODE_H = 70;

const MISSING = { indicator: "red", status: "missing" };

function byService(containers, service) {
  return containers?.find((item) => item.service === service) || MISSING;
}

function coreIndicator(containers) {
  return containers?.some((item) => item.role === "core" && item.indicator === "red") ? "red" : "green";
}

// Addresses come from the backend topology registry (the container's expected_ip), not
// from parsed config, so they stay accurate for topologies whose .conf files are not
// parsed. Falls back to the container name when the registry has no address.
function endpoint(container, { withTelnet = false } = {}) {
  const ip = container?.expected_ip;
  if (!ip) return container?.name || "address unavailable";
  if (withTelnet && container?.telnet_port) return `${ip}:${container.telnet_port}`;
  return ip;
}

function Node({ x, y, title, subtitle, indicator, active = false, external = false }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect
        width={NODE_W}
        height={NODE_H}
        rx="16"
        className={`fill-slate-900 ${active ? "stroke-emerald-300" : external ? "stroke-slate-500/50" : "stroke-cyan-400/40"}`}
        strokeWidth={active ? 3 : 1}
        strokeDasharray={external ? "6 6" : undefined}
      />
      <foreignObject x="14" y="14" width={NODE_W - 28} height={NODE_H - 26}>
        <div className="flex h-full items-center gap-3">
          {external ? (
            <span
              role="img"
              aria-label="not monitored"
              title="not monitored"
              className="inline-block h-3 w-3 shrink-0 rounded-full border-2 border-dashed border-slate-500"
            />
          ) : (
            <StatusDot indicator={indicator} />
          )}
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-white">{title}</div>
            <div className="truncate font-mono text-xs text-slate-400">{subtitle}</div>
          </div>
        </div>
      </foreignObject>
    </g>
  );
}

function EdgeLabel({ x, y, children, width = 58 }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect x={-width / 2} y="-13" width={width} height="24" rx="8" className="fill-slate-950/90 stroke-cyan-400/20" />
      <text textAnchor="middle" dominantBaseline="middle" className="fill-slate-200 text-xs font-semibold">
        {children}
      </text>
    </g>
  );
}

function Edge({ from, to, dashed = false, active = false }) {
  const x1 = from.x + NODE_W / 2;
  const y1 = from.y + NODE_H;
  const x2 = to.x + NODE_W / 2;
  const y2 = to.y;
  const stroke = active ? "stroke-emerald-300" : dashed ? "stroke-teal-300/50" : "stroke-cyan-300/60";
  return (
    <path
      d={`M${x1} ${y1} L${x2} ${y2}`}
      className={stroke}
      strokeWidth={active ? 5 : 3}
      strokeDasharray={dashed ? "8 8" : undefined}
      markerEnd={dashed ? undefined : "url(#arrow)"}
    />
  );
}

/**
 * Per-topology layouts.
 *
 * Every node's status comes from the container registry, so a topology renders whether or
 * not its containers exist. Nothing is inferred: the serving-cell highlight is applied
 * only when a telemetry source actually reported one, and a topology whose config is not
 * parsed shows registry addresses rather than invented cell parameters.
 */
function buildDiagram(topology, containers, config, activeCell) {
  const core = { x: 305, y: 20, title: "CN5G", subtitle: "AMF/SMF/UPF", indicator: coreIndicator(containers) };

  if (topology === "f1") {
    const du0Cfg = config?.dus?.[0] || {};
    const du1Cfg = config?.dus?.[1] || {};
    const cu = { ...byService(containers, "cu"), x: 305, y: 165 };
    const du0 = { ...byService(containers, "du0"), x: 165, y: 315 };
    const du1 = { ...byService(containers, "du1"), x: 445, y: 315 };
    const ue = { ...byService(containers, "nr-ue"), x: 305, y: 435 };
    return {
      title: "F1 RFsim topology",
      nodes: [
        core,
        { ...cu, title: "CU", subtitle: endpoint(cu, { withTelnet: true }) },
        {
          ...du0,
          title: "DU0",
          subtitle: du0Cfg.pci != null ? `PCI ${du0Cfg.pci} / ${endpoint(du0)}` : endpoint(du0),
          active: activeCell === "DU0",
        },
        {
          ...du1,
          title: "DU1",
          subtitle: du1Cfg.pci != null ? `PCI ${du1Cfg.pci} / ${endpoint(du1)}` : endpoint(du1),
          active: activeCell === "DU1",
        },
        { ...ue, title: "RFsim UE", subtitle: endpoint(ue), active: Boolean(activeCell) },
      ],
      edges: [
        { from: core, to: cu },
        { from: cu, to: du0, active: activeCell === "DU0" },
        { from: cu, to: du1, active: activeCell === "DU1" },
        { from: du0, to: ue, dashed: true, active: activeCell === "DU0" },
        { from: du1, to: ue, dashed: true, active: activeCell === "DU1" },
      ],
      labels: [
        { x: 420, y: 130, width: 70, text: "N2/N3" },
        { x: 285, y: 275, width: 42, text: "F1" },
        { x: 475, y: 275, width: 42, text: "F1" },
        { x: 410, y: 408, width: 68, text: "RFsim" },
      ],
    };
  }

  if (topology === "n2-monolithic") {
    const gnb0 = { ...byService(containers, "gnb0"), x: 140, y: 200 };
    const gnb1 = { ...byService(containers, "gnb1"), x: 470, y: 200 };
    const ue = { ...byService(containers, "nr-ue"), x: 305, y: 400 };
    return {
      title: "N2 monolithic RFsim topology",
      nodes: [
        core,
        { ...gnb0, title: "gNB0", subtitle: endpoint(gnb0, { withTelnet: true }), active: activeCell === "gNB0" },
        { ...gnb1, title: "gNB1", subtitle: endpoint(gnb1, { withTelnet: true }), active: activeCell === "gNB1" },
        { ...ue, title: "RFsim UE", subtitle: endpoint(ue), active: Boolean(activeCell) },
      ],
      edges: [
        { from: core, to: gnb0 },
        { from: core, to: gnb1 },
        { from: gnb0, to: ue, dashed: true, active: activeCell === "gNB0" },
        { from: gnb1, to: ue, dashed: true, active: activeCell === "gNB1" },
      ],
      labels: [
        { x: 250, y: 150, width: 70, text: "N2/N3" },
        { x: 512, y: 150, width: 70, text: "N2/N3" },
        { x: 250, y: 345, width: 68, text: "RFsim" },
        { x: 512, y: 345, width: 68, text: "RFsim" },
      ],
    };
  }

  if (topology === "n2-cu-du") {
    const cu0 = { ...byService(containers, "cu0"), x: 110, y: 150 };
    const cu1 = { ...byService(containers, "cu1"), x: 500, y: 150 };
    const du0 = { ...byService(containers, "du0"), x: 110, y: 295 };
    const du1 = { ...byService(containers, "du1"), x: 500, y: 295 };
    const ue = { ...byService(containers, "nr-ue"), x: 305, y: 435 };
    return {
      title: "N2 CU/DU RFsim topology",
      nodes: [
        core,
        { ...cu0, title: "CU0", subtitle: endpoint(cu0, { withTelnet: true }) },
        { ...cu1, title: "CU1", subtitle: endpoint(cu1, { withTelnet: true }) },
        { ...du0, title: "DU0", subtitle: endpoint(du0), active: activeCell === "DU0" },
        { ...du1, title: "DU1", subtitle: endpoint(du1), active: activeCell === "DU1" },
        { ...ue, title: "RFsim UE", subtitle: endpoint(ue), active: Boolean(activeCell) },
      ],
      edges: [
        { from: core, to: cu0 },
        { from: core, to: cu1 },
        { from: cu0, to: du0 },
        { from: cu1, to: du1 },
        { from: du0, to: ue, dashed: true, active: activeCell === "DU0" },
        { from: du1, to: ue, dashed: true, active: activeCell === "DU1" },
      ],
      labels: [
        { x: 235, y: 120, width: 70, text: "N2/N3" },
        { x: 527, y: 120, width: 70, text: "N2/N3" },
        { x: 230, y: 262, width: 42, text: "F1" },
        { x: 620, y: 262, width: 42, text: "F1" },
        { x: 250, y: 405, width: 68, text: "RFsim" },
        { x: 512, y: 405, width: 68, text: "RFsim" },
      ],
    };
  }

  if (topology === "usrp-cots") {
    const gnb = { ...byService(containers, "gnb"), x: 305, y: 200 };
    // The UE is an external COTS handset: no container, so nothing to report on it.
    const ue = { x: 305, y: 380 };
    return {
      title: "USRP X310 single-cell topology",
      nodes: [
        core,
        { ...gnb, title: "gNB", subtitle: "USRP X310", indicator: gnb.indicator },
        { ...ue, title: "COTS UE", subtitle: "not monitored", external: true },
      ],
      edges: [
        { from: core, to: gnb },
        { from: gnb, to: ue, dashed: true },
      ],
      labels: [
        { x: 450, y: 150, width: 70, text: "N2/N3" },
        { x: 450, y: 330, width: 46, text: "Uu" },
      ],
    };
  }

  return null;
}

export default function TopologyDiagram({ containers = [], config = {}, activeDu = null, topology = "f1" }) {
  const diagram = buildDiagram(topology, containers, config, activeDu);

  if (!diagram) {
    return (
      <div className="card h-full p-5">
        <h3 className="text-lg font-semibold text-white">Topology</h3>
        <p className="mt-3 text-sm text-slate-400">
          No diagram is defined for {topology}. Container health is shown in the sidebar.
        </p>
      </div>
    );
  }

  const mobile = topology !== "usrp-cots";

  return (
    <div className="card h-full p-5">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-white">{diagram.title}</h3>
      </div>
      <svg viewBox="0 0 760 520" className="h-[520px] w-full" role="img" aria-label={diagram.title}>
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
            <path d="M0,0 L0,6 L9,3 z" className="fill-cyan-300/60" />
          </marker>
        </defs>
        {diagram.edges.map((edge, index) => (
          <Edge key={`edge-${index}`} {...edge} />
        ))}
        {diagram.nodes.map((node, index) => (
          <Node key={node.title || `node-${index}`} {...node} />
        ))}
        {diagram.labels.map((label, index) => (
          <EdgeLabel key={`label-${index}`} x={label.x} y={label.y} width={label.width}>
            {label.text}
          </EdgeLabel>
        ))}
      </svg>
      {mobile && !activeDu ? (
        <p className="mt-2 text-xs text-slate-500">
          Serving cell not observed — no current telemetry source reports it, so no path is highlighted.
        </p>
      ) : null}
      {topology !== "f1" && topology !== "usrp-cots" ? (
        <p className="mt-1 text-xs text-slate-500">
          Addresses are from the topology registry; cell configuration parsing is F1-only.
        </p>
      ) : null}
    </div>
  );
}
