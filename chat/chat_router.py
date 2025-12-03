from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlmodel import Session
from typing import List, Optional
import json
from datetime import datetime

from database import get_session
from models import (
    Chat, Message, ChatCreate, ChatResponse, 
    MessageCreate, MessageResponse, ChatWithMessages
)
from chat_service import ChatService
from websocket_manager import manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/chats", response_model=ChatResponse)
def create_chat(
    chat_data: ChatCreate,
    session: Session = Depends(get_session)
):
    """Создать новый чат"""
    chat = ChatService.create_chat(session, chat_data)
    
    return ChatResponse(
        id=chat.id,
        iphone_id=chat.iphone_id,
        seller_id=chat.seller_id,
        buyer_id=chat.buyer_id,
        buyer_is_registered=chat.buyer_is_registered,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        unread_count=0
    )


@router.get("/chats/my", response_model=List[ChatResponse])
def get_my_chats(
    user_id: str = Query(..., description="ID пользователя или UUID"),
    is_seller: bool = Query(False, description="Получить чаты где пользователь продавец"),
    session: Session = Depends(get_session)
):
    """Получить все чаты пользователя"""
    chats = ChatService.get_user_chats(session, user_id, is_seller)
    return chats


@router.get("/chats/find")
def find_chat(
    iphone_id: int = Query(..., description="ID объявления"),
    seller_id: int = Query(..., description="ID продавца"),
    buyer_id: str = Query(..., description="ID покупателя или UUID"),
    session: Session = Depends(get_session)
):
    """Найти существующий чат или вернуть null"""
    chat = ChatService.get_or_create_chat(
        session=session,
        iphone_id=iphone_id,
        seller_id=seller_id,
        buyer_id=buyer_id,
        buyer_is_registered=True  # Будет определяться по формату buyer_id
    )
    
    if chat:
        return ChatResponse(
            id=chat.id,
            iphone_id=chat.iphone_id,
            seller_id=chat.seller_id,
            buyer_id=chat.buyer_id,
            buyer_is_registered=chat.buyer_is_registered,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            unread_count=0
        )
    
    return None


@router.get("/chats/seller/{seller_id}/grouped")
def get_seller_chats_grouped(
    seller_id: int,
    session: Session = Depends(get_session)
):
    """Получить чаты продавца, сгруппированные по объявлениям"""
    grouped_chats = ChatService.get_seller_chats_grouped(session, seller_id)
    return grouped_chats


@router.get("/chats/{chat_id}/info", response_model=ChatResponse)
def get_chat_info(
    chat_id: int,
    session: Session = Depends(get_session)
):
    """Получить информацию о чате (без сообщений)"""
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return ChatResponse(
        id=chat.id,
        iphone_id=chat.iphone_id,
        seller_id=chat.seller_id,
        buyer_id=chat.buyer_id,
        buyer_is_registered=chat.buyer_is_registered,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        unread_count=0
    )


@router.get("/chats/{chat_id}", response_model=ChatWithMessages)
def get_chat(
    chat_id: int,
    session: Session = Depends(get_session)
):
    """Получить чат с сообщениями"""
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = ChatService.get_chat_messages(session, chat_id)
    
    return ChatWithMessages(
        id=chat.id,
        iphone_id=chat.iphone_id,
        seller_id=chat.seller_id,
        buyer_id=chat.buyer_id,
        buyer_is_registered=chat.buyer_is_registered,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        unread_count=0,
        messages=[
            MessageResponse(
                id=msg.id,
                chat_id=msg.chat_id,
                sender_id=msg.sender_id,
                sender_is_registered=msg.sender_is_registered,
                message_text=msg.message_text,
                is_read=msg.is_read,
                created_at=msg.created_at
            )
            for msg in messages
        ]
    )


@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
def get_chat_messages(
    chat_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session)
):
    """Получить сообщения чата с пагинацией"""
    messages = ChatService.get_chat_messages(session, chat_id, limit, offset)
    
    return [
        MessageResponse(
            id=msg.id,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            sender_is_registered=msg.sender_is_registered,
            message_text=msg.message_text,
            is_read=msg.is_read,
            created_at=msg.created_at
        )
        for msg in messages
    ]


@router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
def send_message(
    chat_id: int,
    message_data: MessageCreate,
    session: Session = Depends(get_session)
):
    """Отправить сообщение в чат (REST endpoint)"""
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    message = ChatService.add_message(session, chat_id, message_data)
    
    return MessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        sender_is_registered=message.sender_is_registered,
        message_text=message.message_text,
        is_read=message.is_read,
        created_at=message.created_at
    )


@router.post("/chats/{chat_id}/read")
def mark_as_read(
    chat_id: int,
    user_id: str = Query(..., description="ID пользователя"),
    session: Session = Depends(get_session)
):
    """Пометить сообщения как прочитанные"""
    count = ChatService.mark_messages_as_read(session, chat_id, user_id)
    return {"marked_as_read": count}


@router.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: int,
    session: Session = Depends(get_session)
):
    """Удалить чат"""
    success = ChatService.delete_chat(session, chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"deleted": True}


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: int,
    user_id: str = Query(..., description="ID пользователя или UUID"),
    session: Session = Depends(get_session)
):
    """
    WebSocket endpoint для real-time чата
    
    Сообщения от клиента должны быть в формате JSON:
    {
        "type": "message",
        "message_text": "Текст сообщения",
        "sender_is_registered": true/false
    }
    
    Или для отметки как прочитанное:
    {
        "type": "read"
    }
    """
    # Проверяем существование чата
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        await websocket.close(code=1008, reason="Chat not found")
        return
    
    # Подключаем пользователя
    await manager.connect(websocket, chat_id, user_id)
    
    try:
        # Отправляем список онлайн пользователей
        online_users = manager.get_active_users(chat_id)
        await manager.send_personal_message(
            json.dumps({
                "type": "online_users",
                "users": online_users
            }),
            websocket
        )
        
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                # Сохраняем сообщение в БД
                message_create = MessageCreate(
                    message_text=message_data["message_text"],
                    sender_id=user_id,
                    sender_is_registered=message_data.get("sender_is_registered", False)
                )
                
                message = ChatService.add_message(session, chat_id, message_create)
                
                # Отправляем сообщение всем участникам чата
                response_data = {
                    "type": "message",
                    "message": {
                        "id": message.id,
                        "chat_id": message.chat_id,
                        "sender_id": message.sender_id,
                        "sender_is_registered": message.sender_is_registered,
                        "message_text": message.message_text,
                        "is_read": message.is_read,
                        "created_at": message.created_at.isoformat()
                    }
                }
                
                # Broadcast всем в чате
                await manager.broadcast_to_chat(chat_id, response_data)
                
            elif message_data.get("type") == "read":
                # Пометить сообщения как прочитанные
                count = ChatService.mark_messages_as_read(session, chat_id, user_id)
                
                # Уведомить других участников
                await manager.broadcast_to_chat(
                    chat_id,
                    {
                        "type": "messages_read",
                        "user_id": user_id,
                        "count": count
                    },
                    exclude=websocket
                )
            
            elif message_data.get("type") == "typing":
                # Уведомление о том, что пользователь печатает
                await manager.broadcast_to_chat(
                    chat_id,
                    {
                        "type": "typing",
                        "user_id": user_id,
                        "is_typing": message_data.get("is_typing", False)
                    },
                    exclude=websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, chat_id)
        
        # Уведомить остальных об отключении
        await manager.broadcast_to_chat(
            chat_id,
            {
                "type": "user_disconnected",
                "user_id": user_id
            }
        )
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, chat_id)
