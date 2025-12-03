/**
 * Chat Module - WebSocket чат для связи с продавцом
 */

class ChatManager {
    constructor() {
        this.ws = null;
        this.chatId = null;
        this.userId = null;
        this.isRegistered = false;
        this.isOpen = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.sellerId = null;
        this.iphoneId = null;
        
        this.initUserId();
        this.createChatUI();
        this.bindEvents();
    }
    
    /**
     * Инициализация или получение ID пользователя
     */
    initUserId() {
        // Проверяем, авторизован ли пользователь
        this.checkAuth().then(userData => {
            if (userData && userData.id) {
                this.userId = userData.id.toString();
                this.isRegistered = true;
                console.log('Пользователь авторизован:', this.userId);
            } else {
                // Генерируем или получаем UUID для анонима
                this.userId = this.getOrCreateAnonymousId();
                this.isRegistered = false;
                console.log('Анонимный пользователь:', this.userId);
            }
        }).catch(error => {
            console.error('Ошибка при проверке авторизации:', error);
            // В случае ошибки используем анонимный режим
            this.userId = this.getOrCreateAnonymousId();
            this.isRegistered = false;
            console.log('Анонимный пользователь (fallback):', this.userId);
        });
    }
    
    /**
     * Проверка авторизации
     */
    async checkAuth() {
        try {
            const response = await fetch('/api/v1/auth/me', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const userData = await response.json();
                console.log('Данные пользователя получены:', userData);
                return userData;
            }
            console.log('Пользователь не авторизован (status:', response.status, ')');
            return null;
        } catch (error) {
            console.error('Ошибка при проверке авторизации:', error);
            return null;
        }
    }
    
    /**
     * Генерация UUID для анонимных пользователей
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
    
    /**
     * Получить или создать ID для анонимного пользователя
     */
    getOrCreateAnonymousId() {
        let anonymousId = localStorage.getItem('anonymous_user_id');
        
        if (!anonymousId) {
            anonymousId = this.generateUUID();
            localStorage.setItem('anonymous_user_id', anonymousId);
        }
        
        return anonymousId;
    }
    
    /**
     * Создание UI чата
     */
    createChatUI() {
        const chatHTML = `
            <div id="chatModal" class="chat-modal">
                <div class="chat-container">
                    <div class="chat-header">
                        <div class="chat-header-info">
                            <h3 id="chatHeaderTitle">Чат с продавцом</h3>
                            <span id="chatOnlineStatus" class="chat-online-status">●</span>
                        </div>
                        <button id="closeChatBtn" class="chat-close-btn">×</button>
                    </div>
                    
                    <div id="chatMessages" class="chat-messages">
                        <div class="chat-loading">Загрузка...</div>
                    </div>
                    
                    <div class="chat-input-container">
                        <div id="typingIndicator" class="typing-indicator" style="display: none;">
                            <span></span><span></span><span></span>
                        </div>
                        <div class="chat-input-wrapper">
                            <textarea 
                                id="chatMessageInput" 
                                class="chat-input" 
                                placeholder="Написать сообщение..."
                                rows="1"
                            ></textarea>
                            <button id="sendMessageBtn" class="chat-send-btn">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="22" y1="2" x2="11" y2="13"></line>
                                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', chatHTML);
    }
    
    /**
     * Привязка событий
     */
    bindEvents() {
        const closeChatBtn = document.getElementById('closeChatBtn');
        const sendMessageBtn = document.getElementById('sendMessageBtn');
        const messageInput = document.getElementById('chatMessageInput');
        const chatModal = document.getElementById('chatModal');
        
        closeChatBtn.addEventListener('click', () => this.closeChat());
        sendMessageBtn.addEventListener('click', () => this.sendMessage());
        
        // Отправка по Enter (Shift+Enter для новой строки)
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Индикатор печатания
        let typingTimeout;
        messageInput.addEventListener('input', () => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'typing',
                    is_typing: true
                }));
                
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(() => {
                    this.ws.send(JSON.stringify({
                        type: 'typing',
                        is_typing: false
                    }));
                }, 1000);
            }
        });
        
        // Авто-resize textarea
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        // Закрытие по клику вне модального окна
        chatModal.addEventListener('click', (e) => {
            if (e.target === chatModal) {
                this.closeChat();
            }
        });
    }
    
    /**
     * Открыть чат
     */
    async openChat(sellerId, iphoneId) {
        // Проверяем обязательные параметры
        if (!sellerId || !iphoneId) {
            console.error('openChat: требуются sellerId и iphoneId', { sellerId, iphoneId });
            alert('Не удалось открыть чат: недостаточно данных');
            return;
        }
        
        this.sellerId = sellerId;
        this.iphoneId = iphoneId;
        this.chatId = null;
        
        // Ждем инициализации userId если еще не готов
        if (!this.userId) {
            await new Promise(resolve => {
                const checkInterval = setInterval(() => {
                    if (this.userId) {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
            });
        }
        
        // Показываем модальное окно
        document.getElementById('chatModal').classList.add('active');
        document.body.classList.add('modal-open');
        document.body.style.overflow = 'hidden';
        this.isOpen = true;
        
        // Пытаемся найти существующий чат
        console.log('[Chat] Поиск существующего чата...');
        try {
            const response = await fetch(
                `/api/v1/chat/chats/find?iphone_id=${iphoneId}&seller_id=${sellerId}&buyer_id=${this.userId}`
            );
            
            if (response.ok) {
                const chat = await response.json();
                if (chat && chat.id) {
                    this.chatId = chat.id;
                    console.log('[Chat] Найден существующий чат:', this.chatId);
                    
                    // Загружаем историю сообщений
                    await this.loadMessages();
                    
                    // Подключаемся к WebSocket
                    this.connectWebSocket();
                } else {
                    console.log('[Chat] Чат не найден, будет создан при отправке первого сообщения');
                    this.showEmptyChat();
                }
            } else {
                console.log('[Chat] Не удалось найти чат, будет создан при отправке');
                this.showEmptyChat();
            }
        } catch (error) {
            console.error('[Chat] Ошибка при поиске чата:', error);
            this.showEmptyChat();
        }
        
        // Фокус на input
        document.getElementById('chatMessageInput').focus();
    }
    
    showEmptyChat() {
        const container = document.getElementById('chatMessages');
        container.innerHTML = `
            <div class="chat-empty-messages">
                <p>Начните диалог с продавцом</p>
            </div>
        `;
    }
    
    /**
     * Закрыть чат
     */
    closeChat() {
        document.getElementById('chatModal').classList.remove('active');
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        this.isOpen = false;
        
        // Закрываем WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    
    /**
     * Получить или создать чат
     */
    async getOrCreateChat() {
        try {
            const response = await fetch('/api/v1/chat/chats', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    iphone_id: this.iphoneId,
                    seller_id: this.sellerId,
                    buyer_id: this.userId,
                    buyer_is_registered: this.isRegistered
                })
            });
            
            if (response.ok) {
                const chat = await response.json();
                this.chatId = chat.id;
                console.log('Chat ID:', this.chatId);
            } else {
                throw new Error('Не удалось создать чат');
            }
        } catch (error) {
            console.error('Ошибка при создании чата:', error);
            this.showError('Не удалось создать чат. Попробуйте позже.');
        }
    }
    
    /**
     * Загрузить историю сообщений
     */
    async loadMessages() {
        try {
            const response = await fetch(
                `/api/v1/chat/chats/${this.chatId}/messages`
            );
            
            if (response.ok) {
                const messages = await response.json();
                this.displayMessages(messages);
                this.scrollToBottom();
                
                // Помечаем сообщения как прочитанные
                this.markAsRead();
            }
        } catch (error) {
            console.error('Ошибка при загрузке сообщений:', error);
            this.showError('Не удалось загрузить сообщения');
        }
    }
    
    /**
     * Отобразить сообщения
     */
    displayMessages(messages) {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';
        
        if (messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="chat-empty-state">
                    <p>Начните диалог с продавцом</p>
                </div>
            `;
            return;
        }
        
        messages.forEach(message => {
            this.appendMessage(message);
        });
    }
    
    /**
     * Добавить сообщение в UI
     */
    appendMessage(message) {
        const messagesContainer = document.getElementById('chatMessages');
        const isOwnMessage = message.sender_id === this.userId;
        
        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${isOwnMessage ? 'own' : 'other'}`;
        
        const time = new Date(message.created_at).toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        messageEl.innerHTML = `
            <div class="chat-message-bubble">
                <div class="chat-message-text">${this.escapeHtml(message.message_text)}</div>
                <div class="chat-message-time">${time}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageEl);
    }
    
    /**
     * Подключение к WebSocket
     */
    connectWebSocket() {
        if (this.ws) {
            this.ws.close();
        }
        
        // Определяем протокол WebSocket (ws или wss) на основе текущего протокола страницы
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/chat/ws/${this.chatId}?user_id=${this.userId}`;
        console.log('[WebSocket] Попытка подключения...');
        console.log('[WebSocket] Protocol:', wsProtocol);
        console.log('[WebSocket] Host:', window.location.host);
        console.log('[WebSocket] Full URL:', wsUrl);
        console.log('[WebSocket] ChatId:', this.chatId, 'UserId:', this.userId);
        
        try {
            this.ws = new WebSocket(wsUrl);
            console.log('[WebSocket] WebSocket объект создан, readyState:', this.ws.readyState);
        } catch (error) {
            console.error('[WebSocket] Ошибка при создании WebSocket:', error);
            return;
        }
        
        this.ws.onopen = () => {
            console.log('[WebSocket] ✅ Соединение установлено! ReadyState:', this.ws.readyState);
            this.updateOnlineStatus(true);
            this.reconnectAttempts = 0;
        };
        
        this.ws.onmessage = (event) => {
            console.log('[WebSocket] 📩 Получено сообщение:', event.data);
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onerror = (error) => {
            console.error('[WebSocket] ❌ Ошибка соединения:', error);
            console.error('[WebSocket] ReadyState при ошибке:', this.ws.readyState);
            this.updateOnlineStatus(false);
        };
        
        this.ws.onclose = (event) => {
            console.log('[WebSocket] 🔌 Соединение закрыто');
            console.log('[WebSocket] Close code:', event.code, 'Reason:', event.reason);
            console.log('[WebSocket] Was clean:', event.wasClean);
            this.updateOnlineStatus(false);
            
            // Переподключение
            if (this.isOpen && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`Переподключение через ${this.reconnectDelay}ms... (попытка ${this.reconnectAttempts})`);
                setTimeout(() => this.connectWebSocket(), this.reconnectDelay);
            }
        };
    }
    
    /**
     * Обработка WebSocket сообщений
     */
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'message':
                this.appendMessage(data.message);
                this.scrollToBottom();
                
                // Если сообщение не от нас
                if (data.message.sender_id !== this.userId) {
                    // Помечаем как прочитанное
                    this.markAsRead();
                    
                    // Показываем push-уведомление если окно не активно
                    if (window.notificationManager && window.notificationManager.isEnabled()) {
                        const senderName = 'Продавец'; // Можно получить имя из данных
                        window.notificationManager.notifyNewMessage(
                            senderName,
                            data.message.message_text,
                            this.chatId
                        );
                    }
                }
                break;
                
            case 'typing':
                if (data.user_id !== this.userId) {
                    this.showTypingIndicator(data.is_typing);
                }
                break;
                
            case 'online_users':
                console.log('Онлайн пользователи:', data.users);
                break;
                
            case 'messages_read':
                console.log('Сообщения прочитаны:', data.count);
                break;
                
            case 'user_disconnected':
                console.log('Пользователь отключился:', data.user_id);
                break;
        }
    }
    
    /**
     * Отправить сообщение
     */
    async sendMessage() {
        const input = document.getElementById('chatMessageInput');
        const messageText = input.value.trim();
        
        if (!messageText) return;
        
        // Если чата еще нет - создаём
        if (!this.chatId) {
            console.log('[Chat] Создание чата при отправке первого сообщения...');
            await this.getOrCreateChat();
            if (!this.chatId) {
                alert('Не удалось создать чат');
                return;
            }
            
            // Загружаем историю (если есть)
            await this.loadMessages();
            
            // Подключаемся к WebSocket
            this.connectWebSocket();
            
            // Ждём подключения
            await new Promise(resolve => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    resolve();
                } else if (this.ws) {
                    this.ws.addEventListener('open', resolve, { once: true });
                } else {
                    setTimeout(resolve, 1000);
                }
            });
        }
        
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('[Chat] WebSocket не подключен');
            alert('Ошибка подключения к чату');
            return;
        }
        
        const message = {
            type: 'message',
            message_text: messageText,
            sender_is_registered: this.isRegistered
        };
        
        this.ws.send(JSON.stringify(message));
        
        // Очищаем input
        input.value = '';
        input.style.height = 'auto';
        input.focus();
    }
    
    /**
     * Пометить сообщения как прочитанные
     */
    async markAsRead() {
        try {
            await fetch(
                `/api/v1/chat/chats/${this.chatId}/read?user_id=${this.userId}`,
                { method: 'POST' }
            );
        } catch (error) {
            console.error('Ошибка при отметке прочитанных:', error);
        }
    }
    
    /**
     * Показать индикатор печатания
     */
    showTypingIndicator(show) {
        const indicator = document.getElementById('typingIndicator');
        indicator.style.display = show ? 'flex' : 'none';
        
        if (show) {
            this.scrollToBottom();
        }
    }
    
    /**
     * Обновить статус онлайн
     */
    updateOnlineStatus(isOnline) {
        const statusEl = document.getElementById('chatOnlineStatus');
        statusEl.style.color = isOnline ? '#4CAF50' : '#999';
        statusEl.title = isOnline ? 'Онлайн' : 'Оффлайн';
    }
    
    /**
     * Прокрутить к последнему сообщению
     */
    scrollToBottom() {
        const messagesContainer = document.getElementById('chatMessages');
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 100);
    }
    
    /**
     * Показать ошибку
     */
    showError(message) {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = `
            <div class="chat-error">
                <p>${message}</p>
            </div>
        `;
    }
    
    /**
     * Экранирование HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Инициализация менеджера чата
window.chatManager = new ChatManager();
