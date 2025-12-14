/**
 * Seller Chats Module - Seller chat interface in profile
 */

class SellerChatsManager {
    constructor() {
        this.userId = null;
        this.chats = [];
        this.groupedChats = {};
        this.selectedChatId = null;
        this.cachedIphoneData = {};
        this.lastChatsUpdate = 0;
        this.updateInterval = null;
        
        this.init();
    }
    
    async init() {
        console.log('[SellerChats] ' + (window.i18n?.initialization || 'Инициализация...'));
        
        const userData = await this.checkAuth();
        console.log('[SellerChats] ' + (window.i18n?.user_data || 'Данные пользователя') + ':', userData);
        
        if (!userData) {
            console.log('[SellerChats] User not authorized');
            return;
        }
        
        if (!userData.id) {
            console.error('[SellerChats] userData.id missing!', userData);
            return;
        }
        
        this.userId = userData.id;
        console.log('[SellerChats] userId set:', this.userId);
        
        this.createChatsUI();
        
        console.log('[SellerChats] Chats will be loaded when modal opens');
    }
    
    async checkAuth() {
        const cachedAuth = sessionStorage.getItem('seller_auth');
        if (cachedAuth) {
            const cached = JSON.parse(cachedAuth);
            if (Date.now() - cached.timestamp < 5 * 60 * 1000) {
                console.log('[SellerChats] Using cached auth data');
                return cached.data;
            }
        }
        
        try {
            console.log('[SellerChats] Auth request to auth-service...');
            const response = await fetch('/api/v1/auth/me', {
                credentials: 'include'
            });
            
            console.log('[SellerChats] Auth response status:', response.status);
            
            if (response.ok) {
                const data = await response.json();
                console.log('[SellerChats] Data from auth-service:', data);
                
                sessionStorage.setItem('seller_auth', JSON.stringify({
                    data: data,
                    timestamp: Date.now()
                }));
                
                return data;
            }
            console.log('[SellerChats] User not authorized (status not OK)');
            return null;
        } catch (error) {
            console.error('[SellerChats] Auth check error:', error);
            return null;
        }
    }
    
    createChatsUI() {
        const existingBtn = document.getElementById('openSellerChatsBtn');
        if (existingBtn) return;
        
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
        
        const modalHTML = `
            <div id="sellerChatsModal" class="seller-chats-modal">
                <div class="seller-chats-container">
                    <div class="seller-chats-sidebar">
                        <div class="seller-chats-header">
                            <h2>${window.i18n?.my_chats || 'Мои чаты'}</h2>
                            <button id="closeSellerChatsBtn" class="close-btn">×</button>
                        </div>
                        <div id="sellerChatsList" class="seller-chats-list">
                            <div class="chats-loading">${window.i18n?.chatsLoading || 'Загрузка чатов...'}</div>
                        </div>
                    </div>
                    
                    <div class="seller-chat-panel">
                        <div id="sellerChatEmpty" class="seller-chat-empty">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                            </svg>
                            <p>${window.i18n?.select_chat || 'Выберите чат для общения'}</p>
                        </div>
                        
                        <div id="sellerChatActive" class="seller-chat-active" style="display: none;">
                            <div class="seller-chat-active-header">
                                <button id="backToChatListBtn" class="btn-icon mobile-only" title="${window.i18n?.back || 'Назад'}" style="display: none;">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="19" y1="12" x2="5" y2="12"></line>
                                        <polyline points="12 19 5 12 12 5"></polyline>
                                    </svg>
                                </button>
                                <div class="chat-info">
                                    <h3 id="activeChatBuyerName">${window.i18n?.buyer || 'Покупатель'}</h3>
                                    <span id="activeChatProductName">${window.i18n?.product || 'Товар'}</span>
                                </div>
                                <div class="chat-actions">
                                    <button id="hideChatBtn" class="btn-icon" title="${window.i18n?.hide_chat || 'Скрыть чат'}">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                            <circle cx="12" cy="12" r="3"></circle>
                                            <line x1="3" y1="3" x2="21" y2="21"></line>
                                        </svg>
                                    </button>
                                    <button id="deleteChatBtn" class="btn-icon" title="${window.i18n?.delete_chat || 'Удалить чат'}">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="3 6 5 6 21 6"></polyline>
                                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            
                            <div id="sellerChatMessages" class="seller-chat-messages">
                                <div class="chat-loading">${window.i18n?.messagesLoading || 'Загрузка сообщений...'}</div>
                            </div>
                            
                            <div class="seller-chat-input">
                                <textarea id="sellerChatInput" placeholder="${window.i18n?.writeMessage || 'Написать сообщение...'}" rows="1"></textarea>
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
            console.log('[SellerChats] Loading chats (passed', Math.round(timeSinceUpdate/1000), 'sec)');
            this.loadChats();
        } else {
            console.log('[SellerChats] Using cached chats');
        }
        
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.updateInterval = setInterval(() => {
            console.log('[SellerChats] Auto-updating chats');
            this.loadChats();
        }, 30000);
    }
    
    closeChatsModal() {
        document.getElementById('sellerChatsModal').classList.remove('active');
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        this.selectedChatId = null;
        this.showEmptyState();
        
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
            console.log('[SellerChats] Auto-update stopped');
        }
        
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
            console.log('[SellerChats] loadChats: userId not set');
            return;
        }
        
        console.log('[SellerChats] Loading chats for seller:', this.userId);
        
        try {
            const url = `/api/v1/chat/chats/seller/${this.userId}/grouped`;
            console.log('[SellerChats] Request to:', url);
            
            const response = await fetch(url);
            console.log('[SellerChats] Response status:', response.status);
            
            if (response.ok) {
                this.groupedChats = await response.json();
                this.lastChatsUpdate = Date.now();
                console.log('[SellerChats] Chats received:', this.groupedChats);
                this.renderChats();
                this.updateUnreadBadge();
            } else {
                console.error('[SellerChats] Chats load error:', response.status);
                this.showError(window.i18n?.chatsLoadFailed || 'Не удалось загрузить чаты');
            }
        } catch (error) {
            console.error('[SellerChats] Error loading chats:', error);
            this.showError(window.i18n?.chatsConnectionError || 'Ошибка подключения к серверу чатов');
        }
    }
    
    updateUnreadBadge() {
        const totalUnread = Object.values(this.groupedChats)
            .flat()
            .reduce((sum, chat) => sum + chat.unread_count, 0);
        
        console.log('[SellerChats] Badge update. Total unread:', totalUnread);
        
        const badge = document.getElementById('sellerChatsUnreadBadge');
        if (!badge) {
            console.error('[SellerChats] Element sellerChatsUnreadBadge not found!');
            return;
        }
        
        if (totalUnread > 0) {
            badge.textContent = totalUnread > 99 ? '99+' : totalUnread;
            badge.style.display = 'block';
            console.log('[SellerChats] Badge shown:', badge.textContent);
        } else {
            badge.style.display = 'none';
            console.log('[SellerChats] Badge hidden (no unread)');
        }
    }
    
    async renderChats() {
        const container = document.getElementById('sellerChatsList');
        
        if (!container) return;
        
        const totalChats = Object.values(this.groupedChats).flat().length;
        
        if (totalChats === 0) {
            container.innerHTML = `
                <div class="chats-empty">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <p>${window.i18n?.no_messages_yet || 'У вас пока нет сообщений'}</p>
                </div>
            `;
            return;
        }
        
        const iphoneIds = Object.keys(this.groupedChats);
        const iphoneDataPromises = iphoneIds.map(id => this.getIphoneData(id));
        const iphonesData = await Promise.all(iphoneDataPromises);
        
        const iphonesMap = {};
        iphonesData.forEach(data => {
            if (data) iphonesMap[data.id] = data;
        });
        
        let html = '';
        
        for (const [iphoneId, chats] of Object.entries(this.groupedChats)) {
            const iphoneData = iphonesMap[iphoneId];
            const iphoneName = iphoneData ? 
                `${iphoneData.model} ${iphoneData.memory}GB ${iphoneData.color}` : 
                `${window.i18n?.listing || 'Объявление'} #${iphoneId}`;
            
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
        const lastMessage = chat.last_message || (window.i18n?.no_messages || 'Нет сообщений');
        const lastMessageTime = chat.last_message_time ? 
            this.formatTime(chat.last_message_time) : '';
        
        const buyerName = chat.buyer_is_registered ? 
            `${window.i18n?.buyer || 'Покупатель'} #${chat.buyer_id}` : 
            (window.i18n?.anonymous_buyer || 'Анонимный покупатель');
        
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
        const container = document.getElementById('sellerChatsList');
        if (!container) return;
        
        if (container._chatClickHandler) {
            container.removeEventListener('click', container._chatClickHandler);
        }
        
        container._chatClickHandler = (e) => {
            const chatItem = e.target.closest('.chat-item');
            if (chatItem) {
                const chatId = parseInt(chatItem.dataset.chatId);
                console.log('[SellerChats] Chat click:', chatId);
                this.openChat(chatId);
            }
        };
        
        container.addEventListener('click', container._chatClickHandler);
    }
    
    async openChat(chatId) {
        console.log('[SellerChats] Opening chat:', chatId);
        this.selectedChatId = chatId;
        
        try {
            const response = await fetch(`/api/v1/chat/chats/${chatId}/info`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const chat = await response.json();
            this.currentChat = chat;
            
            this.showActiveChat();
            
            const panel = document.querySelector('.seller-chat-panel');
            if (panel && window.innerWidth <= 900) {
                panel.classList.add('show');
            }
            
            const buyerName = chat.buyer_is_registered ? 
                `${window.i18n?.buyer || 'Покупатель'} #${chat.buyer_id}` : 
                (window.i18n?.anonymous_buyer || 'Анонимный покупатель');
            document.getElementById('activeChatBuyerName').textContent = buyerName;
            
            const iphoneData = await this.getIphoneData(chat.iphone_id);
            const productName = iphoneData ? 
                `${iphoneData.model} ${iphoneData.memory}GB` : 
                `${window.i18n?.product || 'Товар'} #${chat.iphone_id}`;
            document.getElementById('activeChatProductName').textContent = productName;
            
            await this.loadMessages(chatId);
            
            this.connectWebSocket(chatId);
            
            await this.markAsRead(chatId);
            
            console.log('[SellerChats] Chat opened successfully');
        } catch (error) {
            console.error('[SellerChats] Ошибка при открытии чата:', error);
            this.showModal(window.i18n?.error || 'Ошибка', window.i18n?.chatsOpenFailed || 'Не удалось открыть чат');
        }
    }
    
    async loadMessages(chatId) {
        const container = document.getElementById('sellerChatMessages');
        container.innerHTML = `<div class="chat-loading">${window.i18n?.messagesLoading || 'Загрузка сообщений...'}</div>`;
        
        try {
            const response = await fetch(`/api/v1/chat/chats/${chatId}/messages`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const messages = await response.json();
            this.renderMessages(messages);
        } catch (error) {
            console.error('[SellerChats] ' + (window.i18n?.messages_load_error || 'Ошибка загрузки сообщений') + ':', error);
            container.innerHTML = `<div class="chat-error">${window.i18n?.messagesLoadFailed || 'Не удалось загрузить сообщения'}</div>`;
        }
    }
    
    renderMessages(messages) {
        const container = document.getElementById('sellerChatMessages');
        
        if (messages.length === 0) {
            container.innerHTML = `<div class="chat-empty-messages">${window.i18n?.no_messages || 'Нет сообщений'}</div>`;
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
        
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/chat/ws/${chatId}?user_id=${this.userId}`;
        console.log('[SellerChats] Connecting to WebSocket:', wsUrl);
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('[SellerChats] WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            console.log('[SellerChats] WebSocket message received:', event.data);
            const data = JSON.parse(event.data);
            console.log('[SellerChats] Parsed data:', data);
            
            if (data.type === 'message') {
                const messageData = data.message || data;
                this.appendMessage(messageData);
                
                if (messageData.sender_id !== this.userId.toString()) {
                    if (window.notificationManager && window.notificationManager.isEnabled()) {
                        const buyerName = this.currentChat?.buyer_is_registered 
                            ? `${window.i18n?.buyer || 'Покупатель'} #${this.currentChat.buyer_id}` 
                            : (window.i18n?.anonymous_buyer || 'Анонимный покупатель');
                        
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
            console.log('[SellerChats] WebSocket closed');
        };
    }
    
    appendMessage(data) {
        console.log('[SellerChats] appendMessage called with data:', data);
        
        const container = document.getElementById('sellerChatMessages');
        if (!container) {
            console.error('[SellerChats] Messages container not found!');
            return;
        }
        
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
        console.log('[SellerChats] Message added to UI');
    }
    
    async sendMessage() {
        const input = document.getElementById('sellerChatInput');
        const text = input.value.trim();
        
        if (!text || !this.selectedChatId) {
            console.log('[SellerChats] Send cancelled: text=', text, 'chatId=', this.selectedChatId);
            return;
        }
        
        console.log('[SellerChats] Sending message:', text);
        console.log('[SellerChats] WebSocket state:', this.ws ? this.ws.readyState : 'no ws');
        
        try {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                const payload = {
                    type: 'message',
                    message_text: text,
                    sender_is_registered: true
                };
                
                console.log('[SellerChats] Sending payload:', payload);
                this.ws.send(JSON.stringify(payload));
                
                input.value = '';
                input.style.height = 'auto';
                console.log('[SellerChats] Message sent');
            } else {
                console.error('[SellerChats] ' + (window.i18n?.ws_not_connected || 'WebSocket не подключен'));
                this.showModal(window.i18n?.error || 'Ошибка', window.i18n?.connectionLost || 'Соединение с чатом потеряно. Попробуйте переоткрыть чат.');
            }
        } catch (error) {
            console.error('[SellerChats] ' + (window.i18n?.send_error || 'Ошибка отправки') + ':', error);
            this.showModal(window.i18n?.error || 'Ошибка', window.i18n?.sendFailed || 'Не удалось отправить сообщение');
        }
    }
    
    async markAsRead(chatId) {
        try {
            await fetch(`/api/v1/chat/chats/${chatId}/read?user_id=${this.userId}`, {
                method: 'POST'
            });
            this.loadChats();
        } catch (error) {
            console.error('[SellerChats] Mark as read error:', error);
        }
    }
    
    showModal(title, message, onConfirm = null) {
        const modalHTML = `
            <div id="confirmModal" class="confirm-modal-overlay">
                <div class="confirm-modal">
                    <h3>${this.escapeHtml(title)}</h3>
                    <p>${this.escapeHtml(message)}</p>
                    <div class="confirm-modal-buttons">
                        ${onConfirm ? `<button class="btn-confirm">${window.i18n?.yes || 'Да'}</button>` : ''}
                        <button class="btn-cancel">${onConfirm ? (window.i18n?.cancel || 'Отмена') : 'OK'}</button>
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
            window.i18n?.hide_chat || 'Скрыть чат',
            window.i18n?.hide_chat_feature || 'Функция скрытия чатов будет добавлена в следующей версии'
        );
    }
    
    async deleteChat() {
        if (!this.selectedChatId) return;
        
        this.showModal(
            window.i18n?.delete_chat || 'Удалить чат',
            window.i18n?.delete_chat_confirm || 'Удалить этот чат? Это действие нельзя отменить.',
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
                        this.showModal(window.i18n?.success || 'Успешно', window.i18n?.chat_deleted || 'Чат удалён');
                    } else {
                        throw new Error(window.i18n?.deleteFailed || 'Не удалось удалить чат');
                    }
                } catch (error) {
                    console.error('[SellerChats] ' + (window.i18n?.delete_error || 'Ошибка удаления') + ':', error);
                    this.showModal(window.i18n?.error || 'Ошибка', window.i18n?.deleteFailed || 'Не удалось удалить чат');
                }
            }
        );
    }
    
    async getIphoneData(iphoneId) {
        if (this.cachedIphoneData[iphoneId]) {
            console.log('[SellerChats] Using cached data for iPhone', iphoneId);
            return this.cachedIphoneData[iphoneId];
        }
        
        try {
            const response = await fetch(`/api/v1/posts/iphone?id=${iphoneId}`);
            if (response.ok) {
                const data = await response.json();
                this.cachedIphoneData[iphoneId] = data;
                console.log('[SellerChats] iPhone data', iphoneId, 'loaded and cached');
                return data;
            }
            return null;
        } catch (error) {
            console.error('Error loading listing data:', error);
            return null;
        }
    }
    
    formatTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 24 * 60 * 60 * 1000 && now.getDate() === date.getDate()) {
            return date.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.getDate() === yesterday.getDate()) {
            return window.i18n?.yesterday || 'Вчера';
        }
        
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

if (document.getElementById('profilePage')) {
    window.sellerChatsManager = new SellerChatsManager();
}
