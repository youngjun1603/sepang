"""WebSocket 연결 관리자 + 라우터"""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

websocket_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        self.rooms[room].add(websocket)

    def disconnect(self, websocket: WebSocket, room: str):
        self.rooms[room].discard(websocket)
        if not self.rooms[room]:
            del self.rooms[room]

    async def broadcast_to_order(self, order_id: str, message: dict):
        dead = set()
        for ws in self.rooms.get(order_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws, order_id)


manager = ConnectionManager()


@websocket_router.websocket("/ws/orders/{order_id}")
async def order_tracking_ws(websocket: WebSocket, order_id: str):
    await manager.connect(websocket, order_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, order_id)
