from typing import List, Dict, Any
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.agent_connections: Dict[str, WebSocket] = {}

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect_client(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_event(self, event_type: str, data: Any):
        """
        Broadcast fleet status updates, alerts, or telemetry to all connected Web UI clients.
        """
        payload = {"event": event_type, "data": data}
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

    async def broadcast(self, message: Any):
        """
        Broadcast arbitrary JSON message to all connected Web UI clients.
        """
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def register_agent(self, device_id: str, websocket: WebSocket, hostname: str = ""):
        try:
            await websocket.accept()
        except Exception:
            pass
        if device_id:
            clean_id = device_id.strip()
            self.agent_connections[clean_id] = websocket
            self.agent_connections[clean_id.upper()] = websocket
            self.agent_connections[clean_id.lower()] = websocket
        if hostname:
            clean_host = hostname.strip()
            self.agent_connections[clean_host] = websocket
            self.agent_connections[clean_host.upper()] = websocket
            self.agent_connections[clean_host.lower()] = websocket

    def unregister_agent(self, device_id: str, hostname: str = ""):
        keys_to_del = []
        if device_id:
            keys_to_del.extend([device_id, device_id.upper(), device_id.lower()])
        if hostname:
            keys_to_del.extend([hostname, hostname.upper(), hostname.lower()])
        for k in keys_to_del:
            self.agent_connections.pop(k, None)

    def is_agent_connected(self, identifier: str) -> bool:
        if not identifier:
            return False
        clean = identifier.strip()
        for k in [clean, clean.upper(), clean.lower()]:
            if k in self.agent_connections:
                return True
        return False

    async def send_agent_command(self, identifier: str, command: Dict[str, Any]) -> bool:
        if not identifier:
            return False
        clean = identifier.strip()
        ws = None
        for k in [clean, clean.upper(), clean.lower()]:
            if k in self.agent_connections:
                ws = self.agent_connections[k]
                break
        if ws is not None:
            try:
                await ws.send_json(command)
                return True
            except Exception as e:
                print(f"[WS Manager] Error pushing command to agent {identifier}: {e}")
                self.unregister_agent(identifier)
                return False
        return False

ws_manager = ConnectionManager()

