import { useEffect, useRef, useState } from "react";
import { wsUrl } from "../utils/api";

export function useWebSocket() {
  const [state, setState] = useState(null);
  const [connection, setConnection] = useState("connecting");
  const retryRef = useRef(null);

  useEffect(() => {
    let socket;
    let closed = false;

    const connect = () => {
      setConnection("connecting");
      socket = new WebSocket(wsUrl());
      socket.onopen = () => setConnection("connected");
      socket.onmessage = (event) => {
        try {
          setState(JSON.parse(event.data));
        } catch {
          setConnection("bad-message");
        }
      };
      socket.onerror = () => setConnection("error");
      socket.onclose = () => {
        if (closed) return;
        setConnection("reconnecting");
        retryRef.current = window.setTimeout(connect, 1500);
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryRef.current) window.clearTimeout(retryRef.current);
      if (socket) socket.close();
    };
  }, []);

  return { state, connection };
}
