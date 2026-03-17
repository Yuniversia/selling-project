from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, UploadFile, File, Body
from sqlmodel import Session
from typing import List, Optional, Dict, Any
import json
import httpx
import os
from datetime import datetime

from database import get_session
from models import (
    Chat, Message, ChatCreate, ChatResponse, 
    MessageCreate, MessageResponse, ChatWithMessages
)
from push_models import PushSubscriptionCreate, PushSubscriptionResponse
from chat_service import ChatService
from websocket_manager import manager
from cloudflare_r2 import r2_client
from push_service import push_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

# URL posts сервиса для проверки активности объявлений
POSTS_API_URL = os.getenv('POSTS_SERVICE_URL', 'http://localhost:3000')


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
async def find_chat(
    iphone_id: int = Query(..., description="ID объявления"),
    seller_id: int = Query(..., description="ID продавца"),
    buyer_id: str = Query(..., description="ID покупателя или UUID"),
    session: Session = Depends(get_session)
):
    """
    Найти существующий чат или создать новый.
    БЕЗОПАСНОСТЬ: Проверяет активность объявления перед созданием чата.
    """
    # Проверяем активность объявления через posts API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{POSTS_API_URL}/api/v1/posts/{iphone_id}",
                timeout=5.0
            )
            
            if not response.is_success:
                raise HTTPException(
                    status_code=404,
                    detail="Объявление не найдено"
                )
            
            payload = response.json()
            post_data = payload.get("data", {}) if isinstance(payload, dict) else {}
            
            # Запрещаем создание чата для неактивных объявлений
            if not post_data.get("active", False):
                raise HTTPException(
                    status_code=403,
                    detail="Невозможно написать продавцу - объявление неактивно"
                )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=503,
            detail="Сервис объявлений недоступен"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка проверки объявления: {str(e)}"
        )
    
    # Определяем зарегистрирован ли пользователь по формату ID
    # UUID формат: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx (содержит дефисы)
    buyer_is_registered = '-' not in buyer_id
    
    chat = ChatService.get_or_create_chat(
        session=session,
        iphone_id=iphone_id,
        seller_id=seller_id,
        buyer_id=buyer_id,
        buyer_is_registered=buyer_is_registered
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
            message_type=msg.message_type,
            file_url=msg.file_url,
            file_name=msg.file_name,
            file_size=msg.file_size,
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
    
    # Send push notifications ВСЕГДА (даже если чат закрыт)
    try:
        sender_id = message_data.sender_id
        
        # Determine recipient based on sender
        if sender_id == str(chat.seller_id):
            # Seller sent message, notify buyer
            recipient_id = chat.buyer_id
            print(f"[Push REST] Will notify buyer: {recipient_id}")
        else:
            # Buyer sent message, notify seller
            recipient_id = str(chat.seller_id)
            print(f"[Push REST] Will notify seller: {recipient_id}")
        
        # Send push notification
        sender_name = f"User {sender_id}"  # TODO: Get actual user name
        message_text = message.message_text or "Отправил файл"
        
        notification_data = {
            "chatId": chat_id,
            "iphone_id": chat.iphone_id,
            "buyer_is_registered": chat.buyer_is_registered if recipient_id == chat.buyer_id else True
        }
        
        count = push_service.send_chat_notification(
            user_id=recipient_id,
            sender_name=sender_name,
            message_text=message_text,
            chat_id=chat_id,
            data=notification_data
        )
        print(f"[Push REST] Sent {count} notification(s) to {recipient_id}")
        
    except Exception as e:
        print(f"[Push REST] ❌ Error sending push notification: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail message delivery if push fails
    
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


@router.post("/chats/{chat_id}/hide")
async def hide_chat(
    chat_id: int,
    user_id: str = Query(..., description="ID пользователя"),
    session: Session = Depends(get_session)
):
    """
    Скрыть чат для текущего пользователя (мягкое удаление)
    Чат остается в базе данных, но не показывается пользователю
    """
    # Определяем, является ли пользователь продавцом
    chat = ChatService.get_chat_by_id(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    try:
        is_seller = str(chat.seller_id) == user_id
    except:
        is_seller = False
    
    success = ChatService.hide_chat(session, chat_id, user_id, is_seller)
    if not success:
        raise HTTPException(status_code=403, detail="Not authorized to hide this chat")
    
    return {"message": f"Chat {chat_id} hidden successfully"}


@router.post("/chats/hide-for-order")
async def hide_chats_for_order(
    post_id: int = Query(..., description="ID объявления"),
    buyer_id: str = Query(..., description="ID покупателя"),
    session: Session = Depends(get_session)
):
    """
    Скрыть все чаты связанные с заказом (для обоих пользователей)
    Вызывается после подтверждения получения товара
    """
    hidden_count = ChatService.hide_chats_for_order(session, post_id, buyer_id)
    return {
        "message": f"Hidden {hidden_count} chat(s)",
        "hidden_count": hidden_count
    }


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
                
                # Отправляем продавцу через глобальный WebSocket (если он подключен)
                chat = ChatService.get_chat_by_id(session, chat_id)
                if chat:
                    # Если сообщение от покупателя - отправляем продавцу
                    if user_id != str(chat.seller_id):
                        await manager.broadcast_to_seller(chat.seller_id, response_data)
                        print(f"[GlobalWS] Sent message to seller {chat.seller_id} global WebSocket")
                
                # Send push notifications
                # ВСЕГДА отправляем push - Service Worker решит, показывать ли уведомление
                # SW проверит, виден ли чат пользователю (не свернут браузер, окно в фокусе)
                try:
                    chat = ChatService.get_chat_by_id(session, chat_id)
                    
                    print(f"[Push] Sender: {user_id}, Seller: {chat.seller_id}, Buyer: {chat.buyer_id}")
                    
                    # Determine recipients based on sender
                    recipients = []
                    if user_id == str(chat.seller_id):
                        # Seller sent message, notify buyer
                        recipients.append(chat.buyer_id)
                        print(f"[Push] Will notify buyer: {chat.buyer_id}")
                    else:
                        # Buyer sent message, notify seller
                        recipients.append(str(chat.seller_id))
                        print(f"[Push] Will notify seller: {chat.seller_id}")
                    
                    # Send push notifications
                    sender_name = f"User {user_id}"  # TODO: Get actual user name
                    message_text = message.message_text or "Отправил файл"
                    
                    for recipient_id in recipients:
                        print(f"[Push] Sending notification to {recipient_id}: {message_text[:50]}")
                        
                        # Determine notification data based on recipient type
                        notification_data = {
                            "chatId": chat_id,
                            "iphone_id": chat.iphone_id
                        }
                        
                        # If recipient is buyer, check if they are registered
                        if recipient_id == chat.buyer_id:
                            notification_data["buyer_is_registered"] = chat.buyer_is_registered
                        else:
                            # Seller is always registered
                            notification_data["buyer_is_registered"] = True
                        
                        count = push_service.send_chat_notification(
                            user_id=recipient_id,
                            sender_name=sender_name,
                            message_text=message_text,
                            chat_id=chat_id,
                            data=notification_data
                        )
                        print(f"[Push] Sent {count} notification(s) to {recipient_id}")
                        
                except Exception as e:
                    print(f"[Push] ❌ Error sending push notification: {e}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail message delivery if push fails
                
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


@router.websocket("/ws/seller/{seller_id}")
async def seller_global_websocket(
    websocket: WebSocket,
    seller_id: int,
    user_id: str = Query(..., description="ID пользователя (должен совпадать с seller_id)"),
    session: Session = Depends(get_session)
):
    """
    Глобальный WebSocket для продавца - получает уведомления о сообщениях во ВСЕХ его чатах
    
    Этот WebSocket не предназначен для отправки сообщений, только для получения уведомлений.
    Для отправки сообщений используйте обычный /ws/{chat_id} endpoint.
    
    Сообщения от сервера в формате:
    {
        "type": "message",
        "message": {
            "id": 123,
            "chat_id": 456,
            "sender_id": "buyer_uuid",
            "message_text": "Hello",
            ...
        }
    }
    """
    # Проверяем что user_id соответствует seller_id
    if str(seller_id) != str(user_id):
        await websocket.close(code=1008, reason="user_id must match seller_id")
        return
    
    # Подключаем продавца к глобальному WebSocket
    await manager.connect_seller_global(websocket, seller_id)
    
    try:
        # Отправляем приветственное сообщение
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Connected to global chat notifications for seller {seller_id}"
        }))
        
        # Ждем сообщений (но не обрабатываем их - это только для получения уведомлений)
        while True:
            try:
                # Просто держим соединение открытым
                data = await websocket.receive_text()
                # Можно добавить ping/pong для keepalive
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception as e:
                print(f"[GlobalWS] Error receiving from seller {seller_id}: {e}")
                break
    
    except WebSocketDisconnect:
        manager.disconnect_seller_global(websocket, seller_id)
        print(f"[GlobalWS] Seller {seller_id} disconnected")
    
    except Exception as e:
        print(f"[GlobalWS] Error for seller {seller_id}: {e}")
        manager.disconnect_seller_global(websocket, seller_id)


# ==================== Push Notification Endpoints ====================

@router.post("/push/subscribe", response_model=dict)
def subscribe_to_push(
    user_id: str = Query(..., description="User ID or UUID"),
    subscription: dict = Body(..., description="Push subscription object from browser")
):
    """
    Subscribe user to push notifications
    
    Request body example:
    {
        "endpoint": "https://fcm.googleapis.com/...",
        "keys": {
            "p256dh": "...",
            "auth": "..."
        }
    }
    """
    try:
        print(f"[Push Subscribe] Received subscription request for user: {user_id}")
        print(f"[Push Subscribe] Subscription data keys: {subscription.keys()}")
        print(f"[Push Subscribe] Endpoint: {subscription.get('endpoint', 'MISSING')[:80]}...")
        
        subscription_data = PushSubscriptionCreate(**subscription)
        result = push_service.save_subscription(user_id, subscription_data)
        
        if result:
            print(f"[Push Subscribe] ✅ Successfully saved subscription for user {user_id}")
            return {
                "success": True,
                "message": "Push subscription saved successfully"
            }
        else:
            print(f"[Push Subscribe] ❌ Failed to save subscription for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to save subscription")
            
    except Exception as e:
        print(f"Error subscribing to push: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/push/unsubscribe")
def unsubscribe_from_push(
    endpoint: str = Body(..., embed=True, description="Push service endpoint to remove")
):
    """
    Unsubscribe from push notifications
    """
    success = push_service.remove_subscription(endpoint)
    
    if success:
        return {"success": True, "message": "Unsubscribed successfully"}
    else:
        return {"success": False, "message": "Subscription not found"}


@router.get("/push/vapid-public-key")
def get_vapid_public_key():
    """
    Get VAPID public key for push subscription
    """
    if not push_service.vapid_public_key:
        raise HTTPException(
            status_code=503, 
            detail="Push notifications not configured on server"
        )
    
    return {"publicKey": push_service.vapid_public_key}


@router.post("/push/test")
def test_push_notification(
    user_id: str = Query(..., description="User ID to send test notification to")
):
    """
    Send test push notification (for debugging)
    """
    count = push_service.send_notification(
        user_id=user_id,
        title="Test Notification",
        body="This is a test push notification from ss.lv",
        data={"test": True}
    )
    
    return {
        "success": count > 0,
        "sent_count": count,
        "message": f"Sent {count} notifications"
    }
