/**
 * Real-Time WebSocket Client for Northstar Workstation Manager
 * Connects to /ws, handles automatic reconnection, event dispatching, and integrates with Desktop Notifications.
 */

import { notificationService } from './notificationService';

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: { [event: string]: Set<(data: any) => void> } = {};
  private reconnectTimer: any = null;
  private isConnecting = false;

  constructor() {
    if (typeof window !== 'undefined') {
      this.connect();
    }
  }

  public connect() {
    if (typeof window === 'undefined' || this.isConnecting) return;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname || 'localhost';
      const port = window.location.port === '5173'
        ? (import.meta.env.VITE_API_PORT || '2301')
        : (window.location.port || '2301');
      const wsUrl = `${protocol}//${host}:${port}/ws`;

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnecting = false;
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
        console.log('[WebSocket] Connected to fleet stream:', wsUrl);
      };

      this.ws.onmessage = (event) => {
        try {
          const raw = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
          if (raw && (raw.event || raw.type)) {
            const eventName = raw.event || raw.type;
            const payload = raw.data !== undefined ? raw.data : (raw.payload !== undefined ? raw.payload : raw);
            
            // Trigger browser desktop notification on new incoming alert
            if (eventName === 'alert.created' && payload) {
              notificationService.notifyAlert(payload);
            } else if (eventName === 'hardware.change' && payload) {
              notificationService.notifyHardwareMismatch(
                payload.deviceName || payload.deviceId || 'ПК',
                payload.component || 'Железо',
                `${payload.changeType || 'Изменение'}: ${payload.previousValue || ''} ➔ ${payload.currentValue || ''}`
              );
            }

            this.emit(eventName, payload);
          }
        } catch {
          // Plain text or ping pong message
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        this.isConnecting = false;
        console.warn('[WebSocket] Stream error, will reconnect...', err);
        try {
          this.ws?.close();
        } catch {}
      };
    } catch (err) {
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  public on(event: string, callback: (data: any) => void): () => void {
    if (!this.listeners[event]) {
      this.listeners[event] = new Set();
    }
    this.listeners[event].add(callback);
    return () => {
      this.listeners[event]?.delete(callback);
    };
  }

  public emit(event: string, data: any) {
    this.listeners[event]?.forEach((cb) => {
      try {
        cb(data);
      } catch (err) {
        console.error(`[WebSocket error in callback for ${event}]`, err);
      }
    });

    this.listeners['*']?.forEach((cb) => {
      try {
        cb({ event, data });
      } catch {}
    });
  }

  public send(msg: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  }
}

export const wsClient = new WebSocketClient();
