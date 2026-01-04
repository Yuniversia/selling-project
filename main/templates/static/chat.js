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
        this.selectedFiles = [];
        this.userIdPromise = null; // Для ожидания инициализации
        
        this.userIdPromise = this.initUserId();
        this.createChatUI();
        this.bindEvents();
    }
    
    /**
     * Инициализация или получение ID пользователя
     */
    async initUserId() {
        try {
            // Проверяем, авторизован ли пользователь
            const userData = await this.checkAuth();
            
            if (userData && userData.id) {
                this.userId = userData.id.toString();
                this.isRegistered = true;
                console.log('[Chat] Пользователь авторизован:', this.userId);
            } else {
                // Генерируем или получаем UUID для анонима
                this.userId = this.getOrCreateAnonymousId();
                this.isRegistered = false;
                console.log('[Chat] Анонимный пользователь:', this.userId);
            }
            
            // После инициализации userId, автоматически подписываемся на push
            this.autoSubscribeToPush();
            
        } catch (error) {
            console.error('[Chat] Ошибка при проверке авторизации:', error);
            // В случае ошибки используем анонимный режим
            this.userId = this.getOrCreateAnonymousId();
            this.isRegistered = false;
            console.log('[Chat] Анонимный пользователь (fallback):', this.userId);
            
            // Пытаемся подписаться даже для анонимных
            this.autoSubscribeToPush();
        }
        
        return this.userId;
    }
    
    /**
     * Автоматическая подписка на push-уведомления
     */
    autoSubscribeToPush() {
        if (!this.userId) return;
        
        // Проверяем, есть ли уже разрешение
        if (window.notificationManager && window.notificationManager.getPermission() === 'granted') {
            // Если разрешение есть, но подписки нет - создаем
            window.notificationManager.checkExistingSubscription().then(() => {
                if (!window.notificationManager.subscription) {
                    console.log('[Chat] Автоподписка на push для пользователя:', this.userId);
                    window.notificationManager.subscribeToPush();
                }
            });
        }
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
        // Проверяем что элемент body существует
        if (!document.body) {
            console.log('[Chat] Skipping UI creation - no body element (non-chat page)');
            return;
        }
        
        const chatHTML = `
            <div id="chatModal" class="chat-modal">
                <div class="chat-container">
                    <div class="chat-header">
                        <div class="chat-header-info">
                            <h3 id="chatHeaderTitle">${window.i18n?.chatWithSeller || 'Чат с продавцом'}</h3>
                            <span id="chatOnlineStatus" class="chat-online-status">●</span>
                        </div>
                        <button id="closeChatBtn" class="chat-close-btn">×</button>
                    </div>
                    
                    <div id="chatMessages" class="chat-messages">
                        <div class="chat-loading">${window.i18n?.loading || 'Загрузка...'}</div>
                    </div>
                    
                    <div class="chat-input-container">
                        <div id="typingIndicator" class="typing-indicator" style="display: none;">
                            <span></span><span></span><span></span>
                        </div>
                        <div id="filePreviewContainer" class="chat-file-preview-scroll" style="display: none;"></div>
                        <div class="chat-input-wrapper">
                            <input type="file" id="chatFileInput" accept="image/*,.pdf" multiple style="display: none;">
                            <button id="attachFileBtn" class="chat-attach-btn" title="Прикрепить файл">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                                </svg>
                            </button>
                            <textarea 
                                id="chatMessageInput" 
                                class="chat-input" 
                                placeholder="${window.i18n?.writeMessage || 'Написать сообщение...'}"
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
        // Проверяем что элементы существуют
        const closeChatBtn = document.getElementById('closeChatBtn');
        const sendMessageBtn = document.getElementById('sendMessageBtn');
        const attachFileBtn = document.getElementById('attachFileBtn');
        const chatFileInput = document.getElementById('chatFileInput');
        const messageInput = document.getElementById('chatMessageInput');
        const chatModal = document.getElementById('chatModal');
        
        // Если элементы не существуют (не на странице с чатом), пропускаем
        if (!closeChatBtn || !sendMessageBtn || !chatModal) {
            console.log('[Chat] Skipping event binding - chat UI not present');
            return;
        }
        
        closeChatBtn.addEventListener('click', () => this.closeChat());
        
        // Прикрепление файла
        if (attachFileBtn && chatFileInput) {
            attachFileBtn.addEventListener('click', () => chatFileInput.click());
            chatFileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }
        
        if (sendMessageBtn) {
            sendMessageBtn.addEventListener('click', () => this.sendMessage());
        }
        
        // Отправка по Enter (Shift+Enter для новой строки)
        if (messageInput) {
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        // Индикатор печатания
        if (messageInput) {
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
        }
        
        // Закрытие по клику вне модального окна
        if (chatModal) {
            chatModal.addEventListener('click', (e) => {
                if (e.target === chatModal) {
                    this.closeChat();
                }
            });
        }
    }
    
    /**
     * Открыть чат
     */
    async openChat(sellerId, iphoneId) {
        // Проверяем обязательные параметры
        if (!sellerId || !iphoneId) {
            console.error('[Chat] openChat: требуются sellerId и iphoneId', { sellerId, iphoneId });
            alert(window.i18n?.insufficientData || 'Не удалось открыть чат: недостаточно данных');
            return;
        }
        
        this.sellerId = sellerId;
        this.iphoneId = iphoneId;
        this.chatId = null;
        
        // Ждем инициализации userId
        if (!this.userId) {
            console.log('[Chat] Ожидание инициализации userId...');
            await this.userIdPromise;
        }
        
        console.log('[Chat] Открытие чата для пользователя:', this.userId, 'isRegistered:', this.isRegistered);
        
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
                    window.currentOpenChatId = this.chatId; // Отслеживание для уведомлений
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
                <p>${window.i18n?.startDialog || 'Начните диалог с продавцом'}</p>
            </div>
        `;
    }
    
    /**
     * Обработка выбора файла
     */
    handleFileSelect(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        
        // Проверка типа и размера файлов
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
        const maxSize = 10 * 1024 * 1024;
        
        const validFiles = [];
        for (const file of files) {
            if (!allowedTypes.includes(file.type)) {
                alert(`Файл ${file.name} имеет неподдерживаемый тип`);
                continue;
            }
            if (file.size > maxSize) {
                alert(`Файл ${file.name} слишком большой (макс. 10 МБ)`);
                continue;
            }
            validFiles.push(file);
        }
        
        if (validFiles.length === 0) return;
        
        this.selectedFiles = validFiles;
        this.showFilesPreviews(validFiles);
    }
    
    /**
     * Показать превью файлов
     */
    showFilesPreviews(files) {
        const previewContainer = document.getElementById('filePreviewContainer');
        previewContainer.innerHTML = '';
        
        files.forEach((file, index) => {
            const previewItem = document.createElement('div');
            previewItem.className = 'file-preview-item';
            
            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.src = e.target.result;
                };
                reader.readAsDataURL(file);
                previewItem.appendChild(img);
            } else {
                const icon = document.createElement('div');
                icon.className = 'file-preview-icon';
                icon.textContent = '📄';
                previewItem.appendChild(icon);
            }
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'file-preview-remove';
            removeBtn.textContent = '×';
            removeBtn.onclick = () => this.removeFileByIndex(index);
            previewItem.appendChild(removeBtn);
            
            previewContainer.appendChild(previewItem);
        });
        
        previewContainer.style.display = 'flex';
    }
    
    /**
     * Удалить файл по индексу
     */
    removeFileByIndex(index) {
        this.selectedFiles.splice(index, 1);
        
        if (this.selectedFiles.length === 0) {
            document.getElementById('chatFileInput').value = '';
            document.getElementById('filePreviewContainer').style.display = 'none';
        } else {
            this.showFilesPreviews(this.selectedFiles);
        }
    }
    
    /**
     * Удалить все файлы
     */
    removeAllFiles() {
        this.selectedFiles = [];
        document.getElementById('chatFileInput').value = '';
        document.getElementById('filePreviewContainer').style.display = 'none';
    }
    
    /**
     * Форматировать размер файла
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    /**
     * Закрыть чат
     */
    closeChat() {
        document.getElementById('chatModal').classList.remove('active');
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        this.isOpen = false;
        window.currentOpenChatId = null; // Очищаем текущий чат
        this.removeAllFiles(); // Очищаем выбранные файлы
        
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
                throw new Error(window.i18n?.createFailed || 'Не удалось создать чат');
            }
        } catch (error) {
            console.error('Ошибка при создании чата:', error);
            this.showError(window.i18n?.createFailed || 'Не удалось создать чат. Попробуйте позже.');
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
            this.showError(window.i18n?.loadMessagesFailed || 'Не удалось загрузить сообщения');
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
                    <p>${window.i18n?.startDialog || 'Начните диалог с продавцом'}</p>
                </div>
            `;
            return;
        }
        
        // Группируем последовательные изображения
        const grouped = this.groupConsecutiveImages(messages);
        
        grouped.forEach(item => {
            if (item.type === 'image_group') {
                this.appendImageGroup(item);
            } else {
                this.appendMessage(item);
            }
        });
        
        // Добавляем обработчики кликов на изображения
        messagesContainer.querySelectorAll('[data-image-url]').forEach(imageEl => {
            imageEl.addEventListener('click', (e) => {
                e.preventDefault();
                const imageUrl = imageEl.dataset.imageUrl;
                this.openImageModal(imageUrl);
            });
        });
    }
    
    /**
     * Группировка последовательных изображений от одного отправителя
     */
    groupConsecutiveImages(messages) {
        const grouped = [];
        let currentGroup = null;
        
        messages.forEach(msg => {
            const isImage = msg.message_type === 'image' && msg.file_url;
            
            if (isImage && currentGroup && currentGroup.sender_id === msg.sender_id) {
                // Добавляем в текущую группу
                currentGroup.images.push(msg);
            } else {
                // Сохраняем предыдущую группу
                if (currentGroup) {
                    grouped.push(currentGroup);
                }
                
                // Создаем новую группу или обычное сообщение
                if (isImage) {
                    currentGroup = {
                        type: 'image_group',
                        sender_id: msg.sender_id,
                        created_at: msg.created_at,
                        images: [msg]
                    };
                } else {
                    grouped.push(msg);
                    currentGroup = null;
                }
            }
        });
        
        // Добавляем последнюю группу
        if (currentGroup) {
            grouped.push(currentGroup);
        }
        
        return grouped;
    }
    
    /**
     * Добавить группу изображений
     */
    appendImageGroup(group) {
        const messagesContainer = document.getElementById('chatMessages');
        const isOwnMessage = group.sender_id === this.userId;
        
        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${isOwnMessage ? 'own' : 'other'}`;
        
        const time = new Date(group.created_at).toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const gridClass = group.images.length === 1 ? 'grid-1' : 
                         group.images.length === 2 ? 'grid-2' :
                         group.images.length === 3 ? 'grid-3' : 'grid-4';
        
        const imagesHTML = group.images.map(img => `
            <div class="grid-image" data-image-url="${img.file_url}">
                <img src="${img.file_url}" alt="${this.escapeHtml(img.file_name || '')}">
            </div>
        `).join('');
        
        messageEl.innerHTML = `
            <div class="chat-message-bubble image-grid ${gridClass}">
                ${imagesHTML}
                <div class="chat-message-time">${time}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageEl);
    }
    
    /**
     * Добавить сообщение в UI
     */
    appendMessage(message) {
        const messagesContainer = document.getElementById('chatMessages');
        const isOwnMessage = message.sender_id === this.userId;
        const isSystemMessage = message.message_type === 'system';
        
        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${isOwnMessage ? 'own' : 'other'} ${isSystemMessage ? 'system' : ''}`;
        
        const time = new Date(message.created_at).toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        let contentHTML = '';
        
        // Системное сообщение
        if (isSystemMessage) {
            contentHTML = `
                <div class="chat-system-message">
                    ${this.escapeHtml(message.message_text || '')}
                    <div class="chat-message-time">${time}</div>
                </div>
            `;
        }
        // Сообщение с изображением
        else if (message.message_type === 'image' && message.file_url) {
            contentHTML = `
                <div class="chat-message-bubble">
                    <div class="chat-message-image" data-image-url="${message.file_url}">
                        <img src="${message.file_url}" alt="${this.escapeHtml(message.file_name || 'Image')}" 
                             style="max-width: 100%; border-radius: 8px; cursor: pointer;">
                    </div>
                    ${message.message_text ? `<div class="chat-message-text">${this.escapeHtml(message.message_text)}</div>` : ''}
                    <div class="chat-message-time">${time}</div>
                </div>
            `;
        }
        // Сообщение с файлом
        else if (message.message_type === 'file' && message.file_url) {
            const fileIcon = message.file_name?.endsWith('.pdf') ? '📄' : '📎';
            contentHTML = `
                <div class="chat-message-bubble">
                    <div class="chat-message-file">
                        <a href="${message.file_url}" target="_blank" class="file-link">
                            <span class="file-icon">${fileIcon}</span>
                            <div class="file-details">
                                <div class="file-name">${this.escapeHtml(message.file_name || 'File')}</div>
                                ${message.file_size ? `<div class="file-size">${this.formatFileSize(message.file_size)}</div>` : ''}
                            </div>
                        </a>
                    </div>
                    ${message.message_text ? `<div class="chat-message-text">${this.escapeHtml(message.message_text)}</div>` : ''}
                    <div class="chat-message-time">${time}</div>
                </div>
            `;
        }
        // Текстовое сообщение
        else {
            contentHTML = `
                <div class="chat-message-bubble">
                    <div class="chat-message-text">${this.escapeHtml(message.message_text || '')}</div>
                    <div class="chat-message-time">${time}</div>
                </div>
            `;
        }
        
        messageEl.innerHTML = contentHTML;
        messagesContainer.appendChild(messageEl);
        
        // Добавляем обработчик клика для изображений
        const imageEl = messageEl.querySelector('[data-image-url]');
        if (imageEl) {
            imageEl.addEventListener('click', (e) => {
                e.preventDefault();
                const imageUrl = imageEl.dataset.imageUrl;
                this.openImageModal(imageUrl);
            });
        }
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
                    
                    // Показываем push-уведомление
                    if (window.notificationManager && window.notificationManager.isEnabled()) {
                        const senderName = 'Продавец'; // Можно получить имя из данных
                        const messageText = data.message.message_text || 'Отправил файл';
                        window.notificationManager.notifyNewMessage(
                            senderName,
                            messageText,
                            this.chatId
                        ).catch(err => {
                            console.warn('[Chat] Ошибка показа уведомления:', err);
                        });
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
        
        // Должен быть либо текст, либо файлы
        if (!messageText && (!this.selectedFiles || this.selectedFiles.length === 0)) return;
        
        // Если чата еще нет - создаём
        if (!this.chatId) {
            console.log('[Chat] Создание чата при отправке первого сообщения...');
            await this.getOrCreateChat();
            if (!this.chatId) {
                alert(window.i18n?.createFailed || 'Не удалось создать чат');
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
            alert(window.i18n?.connectionFailed || 'Ошибка подключения к чату');
            return;
        }
        
        // Если есть файлы - отправляем их по одному
        if (this.selectedFiles && this.selectedFiles.length > 0) {
            try {
                const sendBtn = document.getElementById('sendMessageBtn');
                sendBtn.disabled = true;
                sendBtn.innerHTML = '<span style="font-size: 12px;">⏳</span>';
                
                for (let i = 0; i < this.selectedFiles.length; i++) {
                    const file = this.selectedFiles[i];
                    const fileData = await this.uploadFile(file);
                    
                    const message = {
                        type: 'message',
                        sender_is_registered: this.isRegistered,
                        message_type: file.type.startsWith('image/') ? 'image' : 'file',
                        file_url: fileData.public_url,
                        file_name: file.name,
                        file_size: file.size,
                        message_text: (i === 0 && messageText) ? messageText : null
                    };
                    
                    this.ws.send(JSON.stringify(message));
                    await new Promise(resolve => setTimeout(resolve, 100)); // Небольшая задержка между отправками
                }
                
                this.removeAllFiles();
                input.value = '';
                input.style.height = 'auto';
                
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
            } catch (error) {
                console.error('[Chat] Ошибка при загрузке файлов:', error);
                alert('Ошибка при загрузке файлов');
                const sendBtn = document.getElementById('sendMessageBtn');
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
                return;
            }
        } else if (messageText) {
            // Отправляем только текст
            const message = {
                type: 'message',
                sender_is_registered: this.isRegistered,
                message_text: messageText
            };
            
            this.ws.send(JSON.stringify(message));
            input.value = '';
            input.style.height = 'auto';
        }
    }
    
    /**
     * Загрузить файл на сервер
     */
    async uploadFile(file) {
        try {
            // Загружаем файл напрямую на сервер
            const formData = new FormData();
            formData.append('file', file);
            
            const uploadResponse = await fetch('/api/v1/chat/upload-file', {
                method: 'POST',
                body: formData
            });
            
            if (!uploadResponse.ok) {
                const error = await uploadResponse.json();
                throw new Error(error.detail || 'File upload failed');
            }
            
            const result = await uploadResponse.json();
            console.log('[Chat] File uploaded:', result);
            
            return result;
        } catch (error) {
            console.error('[Chat] Upload error:', error);
            throw error;
        }
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
        statusEl.title = isOnline ? (window.i18n?.online || 'Онлайн') : (window.i18n?.offline || 'Оффлайн');
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
     * Открыть изображение в модальном окне
     */
    openImageModal(imageUrl) {
        let modal = document.getElementById('buyerImageViewModal');
        if (!modal) {
            const modalHTML = `
                <div id="buyerImageViewModal" class="image-view-modal">
                    <span class="image-modal-close">&times;</span>
                    <img class="image-modal-content" id="buyerImageModalImg">
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            modal = document.getElementById('buyerImageViewModal');
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal || e.target.classList.contains('image-modal-close')) {
                    this.closeImageModal();
                }
            });
        }
        
        const img = document.getElementById('buyerImageModalImg');
        img.src = imageUrl;
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
    
    closeImageModal() {
        const modal = document.getElementById('buyerImageViewModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
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
