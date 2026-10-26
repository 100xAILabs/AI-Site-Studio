"""
WebSocket Live Session endpoint for real-time multi-account connection monitoring.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.core.security import decode_token
from jose import JWTError

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
 
    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

@router.websocket("/session")
async def websocket_session_endpoint(
    websocket: WebSocket,
):
    try:
        import asyncio
        import json
        await websocket.accept()
        auth_frame = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        auth_message = json.loads(auth_frame)
        token = auth_message.get("token", "") if auth_message.get("type") == "auth" else ""
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            try:
                await websocket.close(code=4001)
            except Exception:
                pass
            return
    except WebSocketDisconnect:
        return
    except Exception:
        if websocket.application_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=4001)
            except (RuntimeError, WebSocketDisconnect, AttributeError, OSError):
                # Socket already disconnected; AttributeError from stale WebSocketProtocol is harmless
                pass
        return

    if user_id not in manager.active_connections:
        manager.active_connections[user_id] = []
    manager.active_connections[user_id].append(websocket)
    try:
        await manager.send_personal_message(
            {"type": "connected", "user_id": user_id, "status": "authenticated"},
            websocket
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong", "status": "active"})
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
