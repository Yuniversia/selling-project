from fastapi import WebSocket
from typing import Dict, List, Set
import json
from datetime import datetime


class ConnectionManager:
    """Менеджер для управления WebSocket подключениями"""
    
    def __init__(self):
        # {chat_id: [websocket1, websocket2, ...]}
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # {websocket: user_id}
        self.connection_users: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, chat_id: int, user_id: str):
        """Подключить пользователя к чату"""
        await websocket.accept()
        
        if chat_id not in self.active_connections:
            self.active_connections[chat_id] = []
        
        self.active_connections[chat_id].append(websocket)
        self.connection_users[websocket] = user_id
        
        print(f"User {user_id} connected to chat {chat_id}")
        print(f"Active connections in chat {chat_id}: {len(self.active_connections[chat_id])}")
    
    def disconnect(self, websocket: WebSocket, chat_id: int):
        """Отключить пользователя от чата"""
        if chat_id in self.active_connections:
            if websocket in self.active_connections[chat_id]:
                self.active_connections[chat_id].remove(websocket)
                user_id = self.connection_users.get(websocket, "unknown")
                print(f"User {user_id} disconnected from chat {chat_id}")
            
            # Удаляем чат из словаря если никого не осталось
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]
        
        if websocket in self.connection_users:
            del self.connection_users[websocket]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Отправить сообщение конкретному пользователю"""
        await websocket.send_text(message)
    
    async def broadcast_to_chat(self, chat_id: int, message_data: dict, exclude: WebSocket = None):
        """Отправить сообщение всем участникам чата"""
        if chat_id not in self.active_connections:
            print(f"No active connections in chat {chat_id}")
            return
        
        message_json = json.dumps(message_data, default=str)
        
        # Отправляем всем подключенным пользователям в этом чате
        disconnected = []
        for connection in self.active_connections[chat_id]:
            if connection != exclude:  # Не отправляем отправителю
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    print(f"Error sending message: {e}")
                    disconnected.append(connection)
        
        # Удаляем отключенные соединения
        for conn in disconnected:
            self.disconnect(conn, chat_id)
    
    def get_active_users(self, chat_id: int) -> List[str]:
        """Получить список активных пользователей в чате"""
        if chat_id not in self.active_connections:
            return []
        
        return [
            self.connection_users[conn]
            for conn in self.active_connections[chat_id]
            if conn in self.connection_users
        ]
    
    def is_user_online(self, chat_id: int, user_id: str) -> bool:
        """Проверить онлайн ли пользователь в чате"""
        return user_id in self.get_active_users(chat_id)


# Глобальный экземпляр менеджера
manager = ConnectionManager()
