import { Navigate, Route, Routes, useParams } from "react-router-dom";
import NavTabs from "./components/NavTabs";
import ControlsPage from "./pages/ControlsPage";
import Overview from "./pages/Overview";
import ResultsPage from "./pages/ResultsPage";
import { CapabilitiesProvider } from "./hooks/useCapabilities";
import { useWebSocket } from "./hooks/useWebSocket";

// Old bookmarks keep working: the gNB and UE pages folded into Overview, and Handover
// merged into the run explorer under Results.
function RedirectRun() {
  const { runId } = useParams();
  return <Navigate to={runId ? `/results/runs/${runId}` : "/results/runs"} replace />;
}

function RedirectCampaign() {
  const { campaignId } = useParams();
  return <Navigate to={campaignId ? `/results/campaigns/${campaignId}` : "/results/campaigns"} replace />;
}

export default function App() {
  const { state, connection } = useWebSocket();
  return (
    <CapabilitiesProvider>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <NavTabs />
        <Routes>
          <Route path="/" element={<Overview state={state} connection={connection} />} />

          <Route path="/results" element={<Navigate to="/results/runs" replace />} />
          <Route path="/results/runs" element={<ResultsPage state={state} view="runs" />} />
          <Route path="/results/runs/:runId" element={<ResultsPage state={state} view="runs" />} />
          <Route path="/results/campaigns" element={<ResultsPage state={state} view="campaigns" />} />
          <Route path="/results/campaigns/:campaignId" element={<ResultsPage state={state} view="campaigns" />} />

          <Route path="/controls" element={<ControlsPage state={state} />} />

          <Route path="/gnb" element={<Navigate to="/" replace />} />
          <Route path="/ue" element={<Navigate to="/" replace />} />
          <Route path="/handover" element={<Navigate to="/results/runs" replace />} />
          <Route path="/runs" element={<Navigate to="/results/runs" replace />} />
          <Route path="/runs/:runId" element={<RedirectRun />} />
          <Route path="/campaigns" element={<Navigate to="/results/campaigns" replace />} />
          <Route path="/campaigns/:campaignId" element={<RedirectCampaign />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </CapabilitiesProvider>
  );
}
