from sqlmodel import Session, select, func, and_, or_
from typing import List, Optional
from datetime import datetime

from models import Chat, Message, ChatCreate, MessageCreate
from database import get_session


class ChatService:
    """Сервис для работы с чатами"""
    
    @staticmethod
    def create_chat(session: Session, chat_data: ChatCreate) -> Chat:
        """Создать новый чат"""
        # Проверяем, существует ли уже чат для этого объявления и покупателя
        existing_chat = session.exec(
            select(Chat).where(
                and_(
                    Chat.iphone_id == chat_data.iphone_id,
                    Chat.buyer_id == chat_data.buyer_id
                )
            )
        ).first()
        
        if existing_chat:
            return existing_chat
        
        chat = Chat(**chat_data.dict())
        session.add(chat)
        session.commit()
        session.refresh(chat)
        return chat
    
    @staticmethod
    def get_chat_by_id(session: Session, chat_id: int) -> Optional[Chat]:
        """Получить чат по ID"""
        return session.get(Chat, chat_id)
    
    @staticmethod
    def get_or_create_chat(
        session: Session,
        iphone_id: int,
        seller_id: int,
        buyer_id: str,
        buyer_is_registered: bool = False
    ) -> Chat:
        """Получить существующий чат или создать новый"""
        chat = session.exec(
            select(Chat).where(
                and_(
                    Chat.iphone_id == iphone_id,
                    Chat.buyer_id == buyer_id
                )
            )
        ).first()
        
        if not chat:
            chat_data = ChatCreate(
                iphone_id=iphone_id,
                seller_id=seller_id,
                buyer_id=buyer_id,
                buyer_is_registered=buyer_is_registered
            )
            chat = ChatService.create_chat(session, chat_data)
        
        return chat
    
    @staticmethod
    def get_user_chats(session: Session, user_id: str, is_seller: bool = False) -> List[dict]:
        """
        Получить все чаты пользователя
        is_seller=True - получить чаты где пользователь продавец
        is_seller=False - получить чаты где пользователь покупатель
        """
        if is_seller:
            # Конвертируем user_id в int для seller_id
            try:
                seller_id_int = int(user_id)
                chats_query = select(Chat).where(Chat.seller_id == seller_id_int)
            except ValueError:
                return []
        else:
            chats_query = select(Chat).where(Chat.buyer_id == user_id)
        
        chats = session.exec(chats_query).all()
        
        result = []
        for chat in chats:
            # Получаем последнее сообщение
            last_message = session.exec(
                select(Message)
                .where(Message.chat_id == chat.id)
                .order_by(Message.created_at.desc())
            ).first()
            
            # Подсчитываем непрочитанные сообщения
            if is_seller:
                # Для продавца считаем непрочитанные сообщения от покупателя
                unread_count = session.exec(
                    select(func.count(Message.id))
                    .where(
                        and_(
                            Message.chat_id == chat.id,
                            Message.is_read == False,
                            Message.sender_id != user_id
                        )
                    )
                ).first() or 0
            else:
                # Для покупателя считаем непрочитанные сообщения от продавца
                unread_count = session.exec(
                    select(func.count(Message.id))
                    .where(
                        and_(
                            Message.chat_id == chat.id,
                            Message.is_read == False,
                            Message.sender_id != user_id
                        )
                    )
                ).first() or 0
            
            chat_dict = {
                "id": chat.id,
                "iphone_id": chat.iphone_id,
                "seller_id": chat.seller_id,
                "buyer_id": chat.buyer_id,
                "buyer_is_registered": chat.buyer_is_registered,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "unread_count": unread_count,
                "last_message": last_message.message_text if last_message else None,
                "last_message_time": last_message.created_at if last_message else None
            }
            result.append(chat_dict)
        
        # Сортируем по времени последнего сообщения
        result.sort(key=lambda x: x["last_message_time"] or x["created_at"], reverse=True)
        return result
    
    @staticmethod
    def get_seller_chats_grouped(session: Session, seller_id: int) -> dict:
        """
        Получить чаты продавца, сгруппированные по объявлениям
        Возвращает: {iphone_id: [chat1, chat2, ...]}
        """
        chats = ChatService.get_user_chats(session, str(seller_id), is_seller=True)
        
        grouped = {}
        for chat in chats:
            iphone_id = chat["iphone_id"]
            if iphone_id not in grouped:
                grouped[iphone_id] = []
            grouped[iphone_id].append(chat)
        
        return grouped
    
    @staticmethod
    def add_message(
        session: Session,
        chat_id: int,
        message_data: MessageCreate
    ) -> Message:
        """Добавить сообщение в чат"""
        message = Message(
            chat_id=chat_id,
            **message_data.dict()
        )
        session.add(message)
        
        # Обновляем время последнего обновления чата
        chat = session.get(Chat, chat_id)
        if chat:
            chat.updated_at = datetime.utcnow()
        
        session.commit()
        session.refresh(message)
        return message
    
    @staticmethod
    def get_chat_messages(
        session: Session,
        chat_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Получить сообщения чата"""
        messages = session.exec(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        ).all()
        
        return list(messages)
    
    @staticmethod
    def mark_messages_as_read(
        session: Session,
        chat_id: int,
        user_id: str
    ) -> int:
        """
        Пометить сообщения как прочитанные
        Помечает все сообщения в чате, которые НЕ от этого пользователя
        """
        messages = session.exec(
            select(Message).where(
                and_(
                    Message.chat_id == chat_id,
                    Message.sender_id != user_id,
                    Message.is_read == False
                )
            )
        ).all()
        
        count = 0
        for message in messages:
            message.is_read = True
            count += 1
        
        session.commit()
        return count
    
    @staticmethod
    def delete_chat(session: Session, chat_id: int) -> bool:
        """Удалить чат и все его сообщения"""
        chat = session.get(Chat, chat_id)
        if not chat:
            return False
        
        # Сначала удаляем все сообщения (важен порядок из-за FK constraint)
        messages = session.exec(
            select(Message).where(Message.chat_id == chat_id)
        ).all()
        
        for message in messages:
            session.delete(message)
        
        # Сохраняем удаление сообщений
        session.flush()
        
        # Теперь удаляем чат
        session.delete(chat)
        session.commit()
        return True
