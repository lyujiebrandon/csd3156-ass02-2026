import config from "../config";
import { getUserId } from "./auth";

let socket = null;
const listeners = new Map();

export async function connectWebSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) return;

  const userId = await getUserId();
  const url = `${config.websocket.url}?user_id=${userId}`;

  socket = new WebSocket(url);

  socket.onopen = () => {
    console.log("[WS] Connected");
    // Keep-alive ping every 5 minutes
    setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ action: "ping" }));
      }
    }, 300000);
  };

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const type = payload.type;
      if (listeners.has(type)) {
        listeners.get(type).forEach((cb) => cb(payload));
      }
      // Wildcard listeners
      if (listeners.has("*")) {
        listeners.get("*").forEach((cb) => cb(payload));
      }
    } catch (e) {
      console.error("[WS] Failed to parse message", e);
    }
  };

  socket.onerror = (err) => console.error("[WS] Error", err);

  socket.onclose = () => {
    console.log("[WS] Disconnected. Reconnecting in 5s...");
    setTimeout(connectWebSocket, 5000);
  };
}

export function onMessage(type, callback) {
  if (!listeners.has(type)) listeners.set(type, new Set());
  listeners.get(type).add(callback);
  // Return unsubscribe function
  return () => listeners.get(type).delete(callback);
}

export function disconnectWebSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
}
