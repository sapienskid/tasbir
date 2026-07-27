/**
 * Socket.IO connection manager.
 *
 * Provides a singleton Socket.IO client that connects to the backend
 * and manages per-task room subscriptions. Auto-reconnects with
 * exponential backoff (built into socket.io-client).
 *
 * Only connects in browser — SSR-safe via dynamic import.
 */

import { browser } from "$app/environment";
import { writable } from "svelte/store";
import { WS_URL } from "$lib/api/config";

export const connectionStatus = writable<"connected" | "disconnected" | "connecting">("disconnected");

let _socket: any = null;
let ioModule: any = null;

async function _loadIO() {
  if (!ioModule) {
    ioModule = await import("socket.io-client");
  }
  return ioModule;
}

export async function getSocket(): Promise<any> {
  if (!browser) return null;
  if (!_socket) {
    const { io } = await _loadIO();
    _socket = io(WS_URL, {
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      autoConnect: false,
    });
    _socket.on("connect", () => connectionStatus.set("connected"));
    _socket.on("disconnect", () => connectionStatus.set("disconnected"));
    _socket.on("connect_error", () => connectionStatus.set("connecting"));
  }
  return _socket;
}

export async function connectSocket() {
  if (!browser) return;
  const s = await getSocket();
  if (s && !s.connected) s.connect();
}

export async function disconnectSocket() {
  if (_socket?.connected) {
    _socket.disconnect();
  }
}

export async function joinTaskRoom(taskId: string) {
  if (!browser) return;
  const s = await getSocket();
  if (!s) return;
  if (s.connected) {
    s.emit("join", { room: taskId });
  } else {
    s.once("connect", () => s.emit("join", { room: taskId }));
  }
}
