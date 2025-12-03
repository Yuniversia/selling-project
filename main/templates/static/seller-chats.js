/**
 * Seller Chats Module - Интерфейс чатов для продавца в профиле
 */

class SellerChatsManager {
    constructor() {
        this.userId = null;
        this.chats = [];
        this.groupedChats = {};
        this.selectedChatId = null;
        this.cachedIphoneData = {}; // Кэш данных об объявлениях
        this.lastChatsUpdate = 0; // Время последнего обновления
        this.updateInterval = null; // Интервал обновления
        
        this.init();
    }
    
    async init() {
        console.log('[SellerChats] Инициализация...');
        
        // Проверяем авторизацию (с кэшем в sessionStorage)
        const userData = await this.checkAuth();
        console.log('[SellerChats] Данные пользователя:', userData);
        
        if (!userData) {
            console.log('[SellerChats] Пользователь не авторизован');
            return;
        }
        
        if (!userData.id) {
            console.error('[SellerChats] userData.id отсутствует!', userData);
            return;
        }
        
        this.userId = userData.id;
        console.log('[SellerChats] userId установлен:', this.userId);
        
        // Создаем UI
        this.createChatsUI();
        
        // НЕ загружаем чаты при инициализации - только при открытии модального окна
        console.log('[SellerChats] Чаты будут загружены при открытии модального окна');
    }
    
    async checkAuth() {
        // Проверяем кэш в sessionStorage (на время сессии)
        const cachedAuth = sessionStorage.getItem('seller_auth');
        if (cachedAuth) {
            const cached = JSON.parse(cachedAuth);
            // Кэш действителен 5 минут
            if (Date.now() - cached.timestamp < 5 * 60 * 1000) {
                console.log('[SellerChats] Используем кэшированные данные авторизации');
                return cached.data;
            }
        }
        
        try {
            console.log('[SellerChats] Запрос авторизации к auth-service...');
            const response = await fetch('/api/v1/auth/me', {
                credentials: 'include'
            });
            
            console.log('[SellerChats] Статус ответа auth:', response.status);
            
            if (response.ok) {
                const data = await response.json();
                console.log('[SellerChats] Данные от auth-service:', data);
                
                // Сохраняем в кэш
                sessionStorage.setItem('seller_auth', JSON.stringify({
                    data: data,
                    timestamp: Date.now()
                }));
                
                return data;
            }
            console.log('[SellerChats] Пользователь не авторизован (статус не OK)');
            return null;
        } catch (error) {
            console.error('[SellerChats] Ошибка проверки авторизации:', error);
            return null;
        }
    }
    
    createChatsUI() {
        // Создаём кнопку открытия чатов
        const existingBtn = document.getElementById('openSellerChatsBtn');
        if (existingBtn) return; // Уже создана
        
        const chatButton = document.createElement('button');
        chatButton.id = 'openSellerChatsBtn';
        chatButton.className = 'seller-chats-float-btn';
        chatButton.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span id="sellerChatsUnreadBadge" class="unread-badge-float" style="display: none;">0</span>
        `;
        chatButton.onclick = () => this.openChatsModal();
        document.body.appendChild(chatButton);
        
        // Создаём модальное окно чатов
        const modalHTML = `
            <div id="sellerChatsModal" class="seller-chats-modal">
                <div class="seller-chats-container">
                    <!-- Левая панель - список чатов -->
                    <div class="seller-chats-sidebar">
                        <div class="seller-chats-header">
                            <h2>Мои чаты</h2>
                            <button id="closeSellerChatsBtn" class="close-btn">×</button>
                        </div>
                        <div id="sellerChatsList" class="seller-chats-list">
                            <div class="chats-loading">Загрузка чатов...</div>
                        </div>
                    </div>
                    
                    <!-- Правая панель - активный чат -->
                    <div class="seller-chat-panel">
                        <div id="sellerChatEmpty" class="seller-chat-empty">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                            </svg>
                            <p>Выберите чат для общения</p>
                        </div>
                        
                        <div id="sellerChatActive" class="seller-chat-active" style="display: none;">
                            <div class="seller-chat-active-header">
                                <button id="backToChatListBtn" class="btn-icon mobile-only" title="Назад" style="display: none;">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="19" y1="12" x2="5" y2="12"></line>
                                        <polyline points="12 19 5 12 12 5"></polyline>
                                    </svg>
                                </button>
                                <div class="chat-info">
                                    <h3 id="activeChatBuyerName">Покупатель</h3>
                                    <span id="activeChatProductName">Товар</span>
                                </div>
                                <div class="chat-actions">
                                    <button id="hideChatBtn" class="btn-icon" title="Скрыть чат">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                            <circle cx="12" cy="12" r="3"></circle>
                                            <line x1="3" y1="3" x2="21" y2="21"></line>
                                        </svg>
                                    </button>
                                    <button id="deleteChatBtn" class="btn-icon" title="Удалить чат">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="3 6 5 6 21 6"></polyline>
                                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            
                            <div id="sellerChatMessages" class="seller-chat-messages">
                                <div class="chat-loading">Загрузка сообщений...</div>
                            </div>
                            
                            <div class="seller-chat-input">
                                <textarea id="sellerChatInput" placeholder="Написать сообщение..." rows="1"></textarea>
                                <button id="sellerSendBtn" class="btn-send">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="22" y1="2" x2="11" y2="13"></line>
                                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.bindModalEvents();
    }
    
    bindModalEvents() {
        const closeBtn = document.getElementById('closeSellerChatsBtn');
        const modal = document.getElementById('sellerChatsModal');
        const sendBtn = document.getElementById('sellerSendBtn');
        const input = document.getElementById('sellerChatInput');
        const hideBtn = document.getElementById('hideChatBtn');
        const deleteBtn = document.getElementById('deleteChatBtn');
        const backBtn = document.getElementById('backToChatListBtn');
        
        closeBtn.addEventListener('click', () => this.closeChatsModal());
        
        // Кнопка "Назад" для мобильных
        backBtn.addEventListener('click', () => {
            const panel = document.querySelector('.seller-chat-panel');
            if (panel) {
                panel.classList.remove('show');
            }
            this.showEmptyState();
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.closeChatsModal();
        });
        
        sendBtn.addEventListener('click', () => this.sendMessage());
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Авто-resize textarea
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        hideBtn.addEventListener('click', () => this.hideChat());
        deleteBtn.addEventListener('click', () => this.deleteChat());
    }
    
    openChatsModal() {
        document.getElementById('sellerChatsModal').classList.add('active');
        document.body.classList.add('modal-open');
        document.body.style.overflow = 'hidden';
        
        // Загружаем чаты только если прошло больше 10 секунд с последней загрузки
        const timeSinceUpdate = Date.now() - this.lastChatsUpdate;
        if (timeSinceUpdate > 10000) {
            console.log('[SellerChats] Загрузка чатов (прошло', Math.round(timeSinceUpdate/1000), 'сек)');
            this.loadChats();
        } else {
            console.log('[SellerChats] Используем кэшированные чаты');
        }
        
        // Запускаем автообновление только пока модальное окно открыто
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.updateInterval = setInterval(() => {
            console.log('[SellerChats] Автообновление чатов');
            this.loadChats();
        }, 30000); // Каждые 30 секунд
    }
    
    closeChatsModal() {
        document.getElementById('sellerChatsModal').classList.remove('active');
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        this.selectedChatId = null;
        this.showEmptyState();
        
        // Останавливаем автообновление при закрытии
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
            console.log('[SellerChats] Автообновление остановлено');
        }
        
        // Отключаем WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    
    showEmptyState() {
        document.getElementById('sellerChatEmpty').style.display = 'flex';
        document.getElementById('sellerChatActive').style.display = 'none';
    }
    
    showActiveChat() {
        document.getElementById('sellerChatEmpty').style.display = 'none';
        document.getElementById('sellerChatActive').style.display = 'flex';
    }
    
    async loadChats() {
        if (!this.userId) {
            console.log('[SellerChats] loadChats: userId не установлен');
            return;
        }
        
        console.log('[SellerChats] Загрузка чатов для продавца:', this.userId);
        
        try {
            const url = `/api/v1/chat/chats/seller/${this.userId}/grouped`;
            console.log('[SellerChats] Запрос к:', url);
            
            // Загружаем чаты продавца, сгруппированные по объявлениям
            const response = await fetch(url);
            console.log('[SellerChats] Статус ответа:', response.status);
            
            if (response.ok) {
                this.groupedChats = await response.json();
                this.lastChatsUpdate = Date.now(); // Обновляем время последней загрузки
                console.log('[SellerChats] Получены чаты:', this.groupedChats);
                this.renderChats();
                this.updateUnreadBadge();
            } else {
                console.error('[SellerChats] Ошибка загрузки чатов:', response.status);
                this.showError('Не удалось загрузить чаты');
            }
        } catch (error) {
            console.error('[SellerChats] Ошибка при загрузке чатов:', error);
            this.showError('Ошибка подключения к серверу чатов');
        }
    }
    
    updateUnreadBadge() {
        const totalUnread = Object.values(this.groupedChats)
            .flat()
            .reduce((sum, chat) => sum + chat.unread_count, 0);
        
        console.log('[SellerChats] Обновление бейджа. Всего непрочитанных:', totalUnread);
        
        const badge = document.getElementById('sellerChatsUnreadBadge');
        if (!badge) {
            console.error('[SellerChats] Элемент sellerChatsUnreadBadge не найден!');
            return;
        }
        
        if (totalUnread > 0) {
            badge.textContent = totalUnread > 99 ? '99+' : totalUnread;
            badge.style.display = 'block';
            console.log('[SellerChats] Бейдж показан:', badge.textContent);
        } else {
            badge.style.display = 'none';
            console.log('[SellerChats] Бейдж скрыт (нет непрочитанных)');
        }
    }
    
    async renderChats() {
        const container = document.getElementById('sellerChatsList');
        
        if (!container) return;
        
        // Проверяем, есть ли чаты
        const totalChats = Object.values(this.groupedChats).flat().length;
        
        if (totalChats === 0) {
            container.innerHTML = `
                <div class="chats-empty">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <p>У вас пока нет сообщений</p>
                </div>
            `;
            return;
        }
        
        // Загружаем информацию об объявлениях
        const iphoneIds = Object.keys(this.groupedChats);
        const iphoneDataPromises = iphoneIds.map(id => this.getIphoneData(id));
        const iphonesData = await Promise.all(iphoneDataPromises);
        
        const iphonesMap = {};
        iphonesData.forEach(data => {
            if (data) iphonesMap[data.id] = data;
        });
        
        // Рендерим группы чатов
        let html = '';
        
        for (const [iphoneId, chats] of Object.entries(this.groupedChats)) {
            const iphoneData = iphonesMap[iphoneId];
            const iphoneName = iphoneData ? 
                `${iphoneData.model} ${iphoneData.memory}GB ${iphoneData.color}` : 
                `Объявление #${iphoneId}`;
            
            const totalUnread = chats.reduce((sum, chat) => sum + chat.unread_count, 0);
            const isCollapsed = localStorage.getItem(`chat-group-${iphoneId}-collapsed`) === 'true';
            
            html += `
                <div class="chat-group ${isCollapsed ? 'collapsed' : ''}" data-iphone-id="${iphoneId}">
                    <div class="chat-group-header" onclick="window.sellerChatsManager.toggleGroup(${iphoneId})">
                        <div class="chat-group-toggle">
                            <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </div>
                        <div class="chat-group-title">
                            ${this.escapeHtml(iphoneName)}
                            ${totalUnread > 0 ? `<span class="unread-badge">${totalUnread}</span>` : ''}
                        </div>
                        <div class="chat-group-count">${chats.length}</div>
                    </div>
                    <div class="chat-list">
                        ${chats.map(chat => this.renderChatItem(chat)).join('')}
                    </div>
                </div>
            `;
        }
        
        container.innerHTML = html;
        
        // Привязываем события
        this.bindChatEvents();
    }
    
    toggleGroup(iphoneId) {
        const group = document.querySelector(`.chat-group[data-iphone-id="${iphoneId}"]`);
        if (!group) return;
        
        const isCollapsed = group.classList.toggle('collapsed');
        localStorage.setItem(`chat-group-${iphoneId}-collapsed`, isCollapsed);
    }
    
    renderChatItem(chat) {
        const isUnread = chat.unread_count > 0;
        const lastMessage = chat.last_message || 'Нет сообщений';
        const lastMessageTime = chat.last_message_time ? 
            this.formatTime(chat.last_message_time) : '';
        
        const buyerName = chat.buyer_is_registered ? 
            `Покупатель #${chat.buyer_id}` : 
            'Анонимный покупатель';
        
        return `
            <div class="chat-item ${isUnread ? 'unread' : ''}" data-chat-id="${chat.id}">
                <div class="chat-item-avatar">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                </div>
                <div class="chat-item-content">
                    <div class="chat-item-header">
                        <div class="chat-item-name">${this.escapeHtml(buyerName)}</div>
                        <div class="chat-item-time">${lastMessageTime}</div>
                    </div>
                    <div class="chat-item-message">
                        ${this.escapeHtml(lastMessage)}
                        ${isUnread ? `<span class="unread-dot">${chat.unread_count}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    bindChatEvents() {
        // Используем делегирование событий для динамически создаваемых элементов
        const container = document.getElementById('sellerChatsList');
        if (!container) return;
        
        // Удаляем старый слушатель если есть
        if (container._chatClickHandler) {
            container.removeEventListener('click', container._chatClickHandler);
        }
        
        // Создаем новый слушатель
        container._chatClickHandler = (e) => {
            // Ищем ближайший .chat-item элемент
            const chatItem = e.target.closest('.chat-item');
            if (chatItem) {
                const chatId = parseInt(chatItem.dataset.chatId);
                console.log('[SellerChats] Клик на чат:', chatId);
                this.openChat(chatId);
            }
        };
        
        container.addEventListener('click', container._chatClickHandler);
    }
    
    async openChat(chatId) {
        console.log('[SellerChats] Открытие чата:', chatId);
        this.selectedChatId = chatId;
        
        try {
            // Получаем данные чата
            const response = await fetch(`/api/v1/chat/chats/${chatId}/info`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const chat = await response.json();
            this.currentChat = chat;
            
            // Показываем активный чат
            this.showActiveChat();
            
            // На мобильных показываем панель чата поверх списка
            const panel = document.querySelector('.seller-chat-panel');
            if (panel && window.innerWidth <= 900) {
                panel.classList.add('show');
            }
            
            // Обновляем заголовок
            const buyerName = chat.buyer_is_registered ? 
                `Покупатель #${chat.buyer_id}` : 
                'Анонимный покупатель';
            document.getElementById('activeChatBuyerName').textContent = buyerName;
            
            // Получаем информацию о товаре
            const iphoneData = await this.getIphoneData(chat.iphone_id);
            const productName = iphoneData ? 
                `${iphoneData.model} ${iphoneData.memory}GB` : 
                `Товар #${chat.iphone_id}`;
            document.getElementById('activeChatProductName').textContent = productName;
            
            // Загружаем сообщения
            await this.loadMessages(chatId);
            
            // Подключаемся к WebSocket
            this.connectWebSocket(chatId);
            
            // Помечаем как прочитанные
            await this.markAsRead(chatId);
            
            console.log('[SellerChats] Чат успешно открыт');
        } catch (error) {
            console.error('[SellerChats] Ошибка при открытии чата:', error);
            this.showModal('Ошибка', 'Не удалось открыть чат');
        }
    }
    
    async loadMessages(chatId) {
        const container = document.getElementById('sellerChatMessages');
        container.innerHTML = '<div class="chat-loading">Загрузка сообщений...</div>';
        
        try {
            const response = await fetch(`/api/v1/chat/chats/${chatId}/messages`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const messages = await response.json();
            this.renderMessages(messages);
        } catch (error) {
            console.error('[SellerChats] Ошибка загрузки сообщений:', error);
            container.innerHTML = '<div class="chat-error">Не удалось загрузить сообщения</div>';
        }
    }
    
    renderMessages(messages) {
        const container = document.getElementById('sellerChatMessages');
        
        if (messages.length === 0) {
            container.innerHTML = '<div class="chat-empty-messages">Нет сообщений</div>';
            return;
        }
        
        let html = '';
        messages.forEach(msg => {
            const isOwn = msg.sender_id === this.userId.toString();
            const time = new Date(msg.created_at).toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
            
            html += `
                <div class="message ${isOwn ? 'own' : 'other'}">
                    <div class="message-bubble">
                        <div class="message-text">${this.escapeHtml(msg.message_text)}</div>
                        <div class="message-time">${time}</div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    }
    
    connectWebSocket(chatId) {
        if (this.ws) {
            this.ws.close();
        }
        
        // Определяем протокол WebSocket (ws или wss) на основе текущего протокола страницы
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/chat/ws/${chatId}?user_id=${this.userId}`;
        console.log('[SellerChats] Подключение к WebSocket:', wsUrl);
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('[SellerChats] WebSocket подключен');
        };
        
        this.ws.onmessage = (event) => {
            console.log('[SellerChats] WebSocket сообщение получено:', event.data);
            const data = JSON.parse(event.data);
            console.log('[SellerChats] Распарсенные данные:', data);
            
            if (data.type === 'message') {
                // Если есть вложенный объект message, используем его
                const messageData = data.message || data;
                this.appendMessage(messageData);
                
                // Показываем push-уведомление если сообщение не от нас и окно не активно
                if (messageData.sender_id !== this.userId.toString()) {
                    if (window.notificationManager && window.notificationManager.isEnabled()) {
                        const buyerName = this.currentChat?.buyer_is_registered 
                            ? `Покупатель #${this.currentChat.buyer_id}` 
                            : 'Анонимный покупатель';
                        
                        window.notificationManager.notifyNewMessage(
                            buyerName,
                            messageData.message_text || messageData.message || '',
                            this.selectedChatId
                        );
                    }
                }
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('[SellerChats] WebSocket error:', error);
        };
        
        this.ws.onclose = () => {
            console.log('[SellerChats] WebSocket закрыт');
        };
    }
    
    appendMessage(data) {
        console.log('[SellerChats] appendMessage вызван с данными:', data);
        
        const container = document.getElementById('sellerChatMessages');
        if (!container) {
            console.error('[SellerChats] Контейнер сообщений не найден!');
            return;
        }
        
        // Проверяем разные форматы данных
        const messageText = data.message_text || data.message || '';
        const senderId = data.sender_id || '';
        
        const isOwn = senderId === this.userId.toString();
        const time = new Date().toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const messageHTML = `
            <div class="message ${isOwn ? 'own' : 'other'}">
                <div class="message-bubble">
                    <div class="message-text">${this.escapeHtml(messageText)}</div>
                    <div class="message-time">${time}</div>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', messageHTML);
        container.scrollTop = container.scrollHeight;
        console.log('[SellerChats] Сообщение добавлено в UI');
    }
    
    async sendMessage() {
        const input = document.getElementById('sellerChatInput');
        const text = input.value.trim();
        
        if (!text || !this.selectedChatId) {
            console.log('[SellerChats] Отправка отменена: text=', text, 'chatId=', this.selectedChatId);
            return;
        }
        
        console.log('[SellerChats] Отправка сообщения:', text);
        console.log('[SellerChats] WebSocket состояние:', this.ws ? this.ws.readyState : 'нет ws');
        
        try {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                const payload = {
                    type: 'message',
                    message_text: text,
                    sender_is_registered: true
                };
                
                console.log('[SellerChats] Отправка payload:', payload);
                this.ws.send(JSON.stringify(payload));
                
                input.value = '';
                input.style.height = 'auto';
                console.log('[SellerChats] Сообщение отправлено');
            } else {
                console.error('[SellerChats] WebSocket не подключен');
                this.showModal('Ошибка', 'Соединение с чатом потеряно. Попробуйте переоткрыть чат.');
            }
        } catch (error) {
            console.error('[SellerChats] Ошибка отправки:', error);
            this.showModal('Ошибка', 'Не удалось отправить сообщение');
        }
    }
    
    async markAsRead(chatId) {
        try {
            await fetch(`/api/v1/chat/chats/${chatId}/read?user_id=${this.userId}`, {
                method: 'POST'
            });
            this.loadChats(); // Обновляем счётчики
        } catch (error) {
            console.error('[SellerChats] Ошибка пометки прочитанным:', error);
        }
    }
    
    showModal(title, message, onConfirm = null) {
        // Создаём модальное окно для подтверждения
        const modalHTML = `
            <div id="confirmModal" class="confirm-modal-overlay">
                <div class="confirm-modal">
                    <h3>${this.escapeHtml(title)}</h3>
                    <p>${this.escapeHtml(message)}</p>
                    <div class="confirm-modal-buttons">
                        ${onConfirm ? '<button class="btn-confirm">Да</button>' : ''}
                        <button class="btn-cancel">${onConfirm ? 'Отмена' : 'OK'}</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        const modal = document.getElementById('confirmModal');
        const confirmBtn = modal.querySelector('.btn-confirm');
        const cancelBtn = modal.querySelector('.btn-cancel');
        
        const closeModal = () => {
            modal.remove();
        };
        
        if (confirmBtn && onConfirm) {
            confirmBtn.addEventListener('click', () => {
                closeModal();
                onConfirm();
            });
        }
        
        cancelBtn.addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }
    
    async hideChat() {
        if (!this.selectedChatId) return;
        
        this.showModal(
            'Скрыть чат',
            'Функция скрытия чатов будет добавлена в следующей версии'
        );
    }
    
    async deleteChat() {
        if (!this.selectedChatId) return;
        
        this.showModal(
            'Удалить чат',
            'Удалить этот чат? Это действие нельзя отменить.',
            async () => {
                try {
                    const response = await fetch(
                        `/api/v1/chat/chats/${this.selectedChatId}`,
                        { method: 'DELETE' }
                    );
                    
                    if (response.ok) {
                        this.showEmptyState();
                        this.selectedChatId = null;
                        await this.loadChats();
                        this.showModal('Успешно', 'Чат удалён');
                    } else {
                        throw new Error('Не удалось удалить чат');
                    }
                } catch (error) {
                    console.error('[SellerChats] Ошибка удаления:', error);
                    this.showModal('Ошибка', 'Не удалось удалить чат');
                }
            }
        );
    }
    
    async getIphoneData(iphoneId) {
        // Проверяем кэш
        if (this.cachedIphoneData[iphoneId]) {
            console.log('[SellerChats] Используем кэшированные данные для iPhone', iphoneId);
            return this.cachedIphoneData[iphoneId];
        }
        
        try {
            const response = await fetch(`/api/v1/posts/iphone?id=${iphoneId}`);
            if (response.ok) {
                const data = await response.json();
                this.cachedIphoneData[iphoneId] = data; // Сохраняем в кэш
                console.log('[SellerChats] Данные iPhone', iphoneId, 'загружены и кэшированы');
                return data;
            }
            return null;
        } catch (error) {
            console.error('Ошибка при загрузке данных объявления:', error);
            return null;
        }
    }
    
    formatTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        
        // Если сегодня - показываем время
        if (diff < 24 * 60 * 60 * 1000 && now.getDate() === date.getDate()) {
            return date.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        // Если вчера
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.getDate() === yesterday.getDate()) {
            return 'Вчера';
        }
        
        // Иначе показываем дату
        return date.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'short'
        });
    }
    
    pluralize(count, one, two, five) {
        let n = Math.abs(count);
        n %= 100;
        if (n >= 5 && n <= 20) return five;
        n %= 10;
        if (n === 1) return one;
        if (n >= 2 && n <= 4) return two;
        return five;
    }
    
    showError(message) {
        const container = document.getElementById('chatsContainer');
        if (container) {
            container.innerHTML = `
                <div class="chats-error">
                    <p>${message}</p>
                </div>
            `;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Инициализация при загрузке страницы профиля
if (document.getElementById('profilePage')) {
    window.sellerChatsManager = new SellerChatsManager();
}
