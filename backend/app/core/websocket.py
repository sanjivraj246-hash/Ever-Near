import json
from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Map user_id to list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Broadcast list for all users or role groups
        self.role_connections: Dict[str, List[WebSocket]] = {"PARENT": [], "FAMILY": []}

    async def connect(self, websocket: WebSocket, user_id: int, role: str = "PARENT"):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        role_key = role.upper()
        if role_key in self.role_connections:
            self.role_connections[role_key].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int, role: str = "PARENT"):
        if user_id in self.active_connections and websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        role_key = role.upper()
        if role_key in self.role_connections and websocket in self.role_connections[role_key]:
            self.role_connections[role_key].remove(websocket)

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    pass

    async def send_to_family_of_parent(self, db, parent_user_id: int, message: dict):
        """Sends WebSocket event strictly to authorized family members of this specific parent."""
        from app.models.entities import FamilyRelationship
        rels = db.query(FamilyRelationship).filter(
            FamilyRelationship.parent_id == parent_user_id,
            FamilyRelationship.status == "APPROVED"
        ).all()
        for r in rels:
            await self.send_personal_message(message, r.family_user_id)

    def send_to_user(self, user_id: int, message: dict):
        """Synchronous wrapper for sending notification to a user without await."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.send_personal_message(message, user_id))
            else:
                loop.run_until_complete(self.send_personal_message(message, user_id))
        except Exception:
            pass

    async def broadcast_role(self, message: dict, role: str):
        role_key = role.upper()
        if role_key in self.role_connections:
            for connection in self.role_connections[role_key]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    pass

    async def broadcast_all(self, message: dict):
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    pass

ws_manager = ConnectionManager()
