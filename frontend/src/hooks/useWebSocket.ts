import { useEffect, useState } from "react";
import { wsUrl } from "../api/client";

export function useWebSocket<T = unknown>(path: string | null) {
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!path) return;
    const socket = new WebSocket(wsUrl(path));
    socket.onopen = () => {
      setConnected(true);
      socket.send("hello");
    };
    socket.onmessage = (event) => setLastMessage(JSON.parse(event.data));
    socket.onclose = () => setConnected(false);
    return () => socket.close();
  }, [path]);

  return { lastMessage, connected };
}

