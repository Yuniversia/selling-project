from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session
from typing import List, Optional, Dict, Any
import json
from datetime import datetime

from database import get_session
from models import (
    Chat, Message, ChatCreate, ChatResponse, 
    MessageCreate, MessageResponse, ChatWithMessages
)
from chat_service import ChatService
from websocket_manager import manager
from cloudflare_r2 import r2_client

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


@router.post("/chats/{chat_id}/invite-support")
def invite_support(
    chat_id: int,
    user_id: str = Query(..., description="ID пользователя, который приглашает поддержку"),
    session: Session = Depends(get_session)
):
    """Пригласить тех поддержку в чат"""
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.support_joined:
        raise HTTPException(status_code=400, detail="Support already joined")
    
    chat.support_joined = True
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Создаем системное сообщение о приглашении поддержки
    system_message = MessageCreate(
        message_text="🛠️ Техническая поддержка приглашена в чат",
        message_type="system",
        sender_id="system",
        sender_is_registered=True
    )
    ChatService.add_message(session, chat_id, system_message)
    
    return {"success": True, "message": "Support invited"}


@router.post("/chats/{chat_id}/join-support")
def join_support(
    chat_id: int,
    support_user_id: int = Query(..., description="ID сотрудника поддержки"),
    session: Session = Depends(get_session)
):
    """Сотрудник поддержки присоединяется к чату"""
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if not chat.support_joined:
        raise HTTPException(status_code=400, detail="Support was not invited")
    
    chat.support_user_id = support_user_id
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Создаем системное сообщение о присоединении поддержки
    system_message = MessageCreate(
        message_text="✅ Техническая поддержка присоединилась к чату",
        message_type="system",
        sender_id="system",
        sender_is_registered=True
    )
    ChatService.add_message(session, chat_id, system_message)
    
    return {"success": True, "message": "Support joined"}


@router.post("/chats/{chat_id}/leave-support")
def leave_support(
    chat_id: int,
    support_user_id: int = Query(..., description="ID сотрудника поддержки"),
    session: Session = Depends(get_session)
):
    """Сотрудник поддержки покидает чат"""
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.support_user_id != support_user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    chat.support_joined = False
    chat.support_user_id = None
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Создаем системное сообщение о выходе поддержки
    system_message = MessageCreate(
        message_text="👋 Техническая поддержка покинула чат",
        message_type="system",
        sender_id="system",
        sender_is_registered=True
    )
    ChatService.add_message(session, chat_id, system_message)
    
    return {"success": True, "message": "Support left"}


@router.get("/chats/support/pending")
def get_pending_support_chats(
    session: Session = Depends(get_session)
):
    """Получить чаты, ожидающие помощи поддержки (для админов/поддержки)"""
    from sqlmodel import select
    
    chats = session.exec(
        select(Chat).where(
            Chat.support_joined == True,
            Chat.support_user_id == None
        )
    ).all()
    
    result = []
    for chat in chats:
        # Получаем информацию о чате
        chat_info = ChatService.get_user_chats(session, str(chat.seller_id), is_seller=True)
        matching_chat = next((c for c in chat_info if c["id"] == chat.id), None)
        if matching_chat:
            result.append(matching_chat)
    
    return result


@router.post("/upload-url")
async def get_file_upload_url(file_name: str = Query(...), content_type: str = Query(...)):
    """
    Получить URL для загрузки файла в чат
    
    Args:
        file_name: имя файла
        content_type: MIME тип файла
    
    Returns:
        {
            "upload_url": "URL для загрузки через сервер",
            "id": "ID файла (object key)",
            "method": "server_upload"
        }
    """
    try:
        upload_data = await r2_client.get_upload_url(file_name)
        return upload_data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting upload URL: {str(e)}"
        )


@router.post("/upload-file")
async def upload_file_to_server(file: UploadFile = File(...)):
    """
    Загрузить файл на сервер (временное решение вместо прямой загрузки в R2)
    
    Returns:
        {
            "file_id": "ID файла",
            "file_name": "имя файла",
            "file_size": размер в байтах,
            "public_url": "публичный URL"
        }
    """
    try:
        # Читаем файл
        file_data = await file.read()
        
        # Генерируем object_key
        import uuid
        import time
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
        object_key = f"chat-files/{timestamp}_{unique_id}.{file_extension}"
        
        # Загружаем файл
        public_url = await r2_client.upload_file_to_r2(
            file_data=file_data,
            object_key=object_key,
            content_type=file.content_type or 'application/octet-stream'
        )
        
        return {
            "file_id": object_key,
            "file_name": file.filename,
            "file_size": len(file_data),
            "public_url": public_url
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("/upload-url")
async def get_file_upload_url_old():
    """Устаревший endpoint для обратной совместимости"""
    raise HTTPException(
        status_code=400,
        detail="Use POST /upload-url with file_name and content_type parameters"
    )


@router.post("/file-uploaded")
def confirm_file_upload(
    file_id: str = Query(..., description="ID загруженного файла"),
    file_name: str = Query(..., description="Имя файла"),
    file_size: int = Query(..., description="Размер файла в байтах")
):
    """
    Подтвердить успешную загрузку файла и получить публичный URL
    
    Returns:
        {
            "public_url": "публичный URL файла",
            "file_id": "ID файла"
        }
    """
    try:
        public_url = r2_client.get_public_url(file_id)
        return {
            "public_url": public_url,
            "file_id": file_id,
            "file_name": file_name,
            "file_size": file_size
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error confirming upload: {str(e)}"
        )


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
                    message_text=message_data.get("message_text"),
                    message_type=message_data.get("message_type", "text"),
                    file_url=message_data.get("file_url"),
                    file_name=message_data.get("file_name"),
                    file_size=message_data.get("file_size"),
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
                        "message_type": message.message_type,
                        "file_url": message.file_url,
                        "file_name": message.file_name,
                        "file_size": message.file_size,
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
            
            elif message_data.get("type") == "invite_support":
                # Приглашение поддержки в чат
                chat = ChatService.get_chat_by_id(session, chat_id)
                if not chat.support_joined:
                    chat.support_joined = True
                    session.add(chat)
                    session.commit()
                    
                    # Создаем системное сообщение
                    system_message = MessageCreate(
                        message_text="🛠️ Техническая поддержка приглашена в чат",
                        message_type="system",
                        sender_id="system",
                        sender_is_registered=True
                    )
                    message = ChatService.add_message(session, chat_id, system_message)
                    
                    # Уведомляем всех участников
                    await manager.broadcast_to_chat(
                        chat_id,
                        {
                            "type": "support_invited",
                            "message": {
                                "id": message.id,
                                "chat_id": message.chat_id,
                                "sender_id": message.sender_id,
                                "message_text": message.message_text,
                                "message_type": message.message_type,
                                "created_at": message.created_at.isoformat()
                            }
                        }
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
