import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiGet } from "../utils/api";

// Action capabilities are fixed for the backend process lifetime (the enable flag is
// read at startup), so they are fetched once and shared. Three separate Overview cards
// used to each fire this request on mount.
const CapabilitiesContext = createContext({ capabilities: null, reload: () => {} });

export function CapabilitiesProvider({ children }) {
  const [capabilities, setCapabilities] = useState(null);

  const reload = useCallback(() => {
    apiGet("/api/actions/capabilities")
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <CapabilitiesContext.Provider value={{ capabilities, reload }}>
      {children}
    </CapabilitiesContext.Provider>
  );
}

export function useCapabilities() {
  return useContext(CapabilitiesContext);
}

// Whether an action supports a topology, derived from the backend capabilities rather
// than a hardcoded topology check.
export function actionSupportsTopology(capabilities, kind, topology) {
  const action = capabilities?.available_actions?.find((item) => item.kind === kind);
  if (!action) return topology === "f1"; // conservative fallback before capabilities load
  if (!action.allowed_topologies) return true;
  return action.allowed_topologies.includes(topology);
}
