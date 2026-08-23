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

    async def register_agent(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.agent_connections[device_id] = websocket

    def unregister_agent(self, device_id: str):
        if device_id in self.agent_connections:
            del self.agent_connections[device_id]

ws_manager = ConnectionManager()
