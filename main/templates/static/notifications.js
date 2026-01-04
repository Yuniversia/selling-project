/**
 * Push Notifications Manager
 * Управление Web Push уведомлениями
 */

class NotificationManager {
    constructor() {
        this.swRegistration = null;
        this.isSupported = 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
        this.permission = this.isSupported ? Notification.permission : 'denied';
        this.subscription = null;
        this.vapidPublicKey = null;
        
        if (this.isSupported) {
            this.init();
        } else {
            console.warn('[Notifications] ' + (window.i18n?.js_notif_not_supported || 'Push-уведомления не поддерживаются браузером'));
        }
    }
    
    async init() {
        try {
            console.log('[Notifications] Starting initialization...');
            
            // Регистрируем Service Worker
            this.swRegistration = await navigator.serviceWorker.register('/templates/static/sw.js', {
                scope: '/'
            });
            
            console.log('[Notifications] ' + (window.i18n?.js_notif_sw_registered || 'Service Worker зарегистрирован:'), this.swRegistration.scope);
            
            // Ждем активации
            await navigator.serviceWorker.ready;
            console.log('[Notifications] ' + (window.i18n?.js_notif_sw_active || 'Service Worker активен'));
            
            // Проверяем текущее разрешение
            this.permission = Notification.permission;
            console.log('[Notifications] Permission status:', this.permission);
            
            // Получаем VAPID public key с сервера
            await this.loadVapidPublicKey();
            
            // Проверяем существующую подписку
            await this.checkExistingSubscription();
            
            console.log('[Notifications] ✅ Initialization complete');
            console.log('[Notifications] Status:', {
                permission: this.permission,
                hasVAPID: !!this.vapidPublicKey,
                hasSubscription: !!this.subscription
            });
            
        } catch (error) {
            console.error('[Notifications] ' + (window.i18n?.js_notif_sw_error || 'Ошибка регистрации Service Worker:'), error);
        }
    }
    
    /**
     * Загрузить VAPID public key с сервера
     */
    async loadVapidPublicKey() {
        try {
            const response = await fetch('/api/v1/chat/push/vapid-public-key');
            if (response.ok) {
                const data = await response.json();
                this.vapidPublicKey = data.publicKey;
                console.log('[Notifications] VAPID public key loaded:', this.vapidPublicKey ? 'OK' : 'MISSING');
            } else {
                console.warn('[Notifications] Could not load VAPID key from server, status:', response.status);
            }
        } catch (error) {
            console.error('[Notifications] Error loading VAPID key:', error);
        }
    }
    
    /**
     * Проверить существующую подписку
     */
    async checkExistingSubscription() {
        if (!this.swRegistration) return;
        
        try {
            this.subscription = await this.swRegistration.pushManager.getSubscription();
            if (this.subscription) {
                console.log('[Notifications] Existing push subscription found');
            }
        } catch (error) {
            console.error('[Notifications] Error checking subscription:', error);
        }
    }
    
    /**
     * Запросить разрешение на уведомления и подписаться на push
     */
    async requestPermission() {
        if (!this.isSupported) {
            console.warn('[Notifications] ' + (window.i18n?.js_notif_not_supported || 'Push-уведомления не поддерживаются'));
            return false;
        }
        
        if (this.permission === 'granted' && this.subscription) {
            console.log('[Notifications] ' + (window.i18n?.js_notif_permission_already || 'Подписка уже активна'));
            return true;
        }
        
        try {
            // Запрашиваем разрешение
            const permission = await Notification.requestPermission();
            this.permission = permission;
            
            if (permission === 'granted') {
                console.log('[Notifications] ' + (window.i18n?.js_notif_permission_granted || 'Разрешение на уведомления получено'));
                
                // Подписываемся на push
                await this.subscribeToPush();
                return true;
            } else {
                console.log('[Notifications] ' + (window.i18n?.js_notif_permission_denied || 'Разрешение на уведомления отклонено'));
                return false;
            }
        } catch (error) {
            console.error('[Notifications] ' + (window.i18n?.js_notif_permission_error || 'Ошибка запроса разрешения:'), error);
            return false;
        }
    }
    
    /**
     * Подписаться на push уведомления
     */
    async subscribeToPush() {
        if (!this.swRegistration || !this.vapidPublicKey) {
            console.warn('[Notifications] Cannot subscribe: no service worker or VAPID key');
            console.warn('[Notifications] SW:', !!this.swRegistration, 'VAPID:', !!this.vapidPublicKey);
            return null;
        }
        
        try {
            console.log('[Notifications] Starting push subscription...');
            
            // Конвертируем VAPID key из base64
            const applicationServerKey = this.urlBase64ToUint8Array(this.vapidPublicKey);
            console.log('[Notifications] VAPID key converted, length:', applicationServerKey.length);
            
            // Создаем подписку
            this.subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            console.log('[Notifications] ✅ Push subscription created');
            console.log('[Notifications] Endpoint:', this.subscription.endpoint.substring(0, 80) + '...');
            
            // Отправляем подписку на сервер
            const userId = this.getUserId();
            if (userId) {
                console.log('[Notifications] Saving subscription for user:', userId);
                await this.saveSubscriptionToServer(userId);
            } else {
                console.error('[Notifications] ❌ Cannot save subscription: no user ID');
            }
            
            return this.subscription;
            
        } catch (error) {
            console.error('[Notifications] ❌ Error subscribing to push:', error);
            return null;
        }
    }
    
    /**
     * Сохранить подписку на сервере
     */
    async saveSubscriptionToServer(userId) {
        if (!this.subscription) return false;
        
        try {
            const response = await fetch(`/api/v1/chat/push/subscribe?user_id=${userId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.subscription.toJSON())
            });
            
            if (response.ok) {
                console.log('[Notifications] Subscription saved to server for user:', userId);
                return true;
            } else {
                console.error('[Notifications] Failed to save subscription:', response.status, await response.text());
                return false;
            }
        } catch (error) {
            console.error('[Notifications] Error saving subscription:', error);
            return false;
        }
    }
    
    /**
     * Отписаться от push уведомлений
     */
    async unsubscribe() {
        if (!this.subscription) {
            console.log('[Notifications] No active subscription to unsubscribe');
            return true;
        }
        
        try {
            // Удаляем подписку локально
            const endpoint = this.subscription.endpoint;
            await this.subscription.unsubscribe();
            this.subscription = null;
            
            // Удаляем подписку на сервере
            await fetch('/api/v1/chat/push/unsubscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ endpoint: endpoint })
            });
            
            console.log('[Notifications] Unsubscribed from push notifications');
            return true;
            
        } catch (error) {
            console.error('[Notifications] Error unsubscribing:', error);
            return false;
        }
    }
    
    /**
     * Показать локальное уведомление (не через push)
     */
    async showNotification(title, options = {}) {
        if (!this.isSupported || this.permission !== 'granted') {
            console.warn('[Notifications] ' + (window.i18n?.js_notif_no_permission || 'Нет разрешения на уведомления'));
            return;
        }
        
        try {
            const defaultOptions = {
                body: window.i18n?.js_notif_new_message || 'У вас новое сообщение',
                icon: '/templates/static/icon-192.png.svg',
                badge: '/templates/static/badge-72.png.svg',
                vibrate: [200, 100, 200],
                tag: 'chat-message',
                requireInteraction: false,
                renotify: true,
                silent: false,
                sound: '/templates/static/sounds/notification.mp3'
            };
            
            const notificationOptions = { ...defaultOptions, ...options };
            
            if (this.swRegistration && this.swRegistration.active) {
                // Показываем через Service Worker
                await this.swRegistration.showNotification(title, notificationOptions);
                console.log('[Notifications] ' + (window.i18n?.js_notif_shown || 'Уведомление показано:'), title);
            } else {
                // Fallback - показываем напрямую
                new Notification(title, notificationOptions);
                console.log('[Notifications] ' + (window.i18n?.js_notif_shown || 'Уведомление показано:'), title);
            }
        } catch (error) {
            console.error('[Notifications] ' + (window.i18n?.js_notif_show_error || 'Ошибка показа уведомления:'), error);
        }
    }
    
    /**
     * Показать уведомление о новом сообщении в чате
     */
    async notifyNewMessage(senderName, messageText, chatId) {
        if (!this.isSupported || this.permission !== 'granted') {
            console.log('[Notifications] Нет разрешения на уведомления');
            return;
        }
        
        // Не показываем уведомление если окно активно И чат открыт
        const isWindowActive = document.visibilityState === 'visible' && !document.hidden;
        const isChatOpen = window.currentOpenChatId && window.currentOpenChatId == chatId;
        
        if (isWindowActive && isChatOpen) {
            console.log('[Notifications] ' + (window.i18n?.js_notif_window_active || 'Окно активно, уведомление не показано'));
            return;
        }
        
        const title = `${window.i18n?.js_notif_new_message_from || 'Новое сообщение от'} ${senderName}`;
        const bodyText = messageText && messageText.length > 0 
            ? (messageText.length > 100 ? messageText.substring(0, 100) + '...' : messageText)
            : (window.i18n?.js_notif_default_body || 'У вас новое сообщение');
        
        const options = {
            body: bodyText,
            icon: '/templates/static/icon-192.png.svg',
            badge: '/templates/static/badge-72.png.svg',
            tag: `chat-${chatId}`,
            renotify: true,
            requireInteraction: false,
            vibrate: [200, 100, 200],
            silent: false,
            sound: '/templates/static/sounds/notification.mp3',
            data: {
                chatId: chatId,
                url: window.location.origin + '/profile'
            },
            actions: [
                {
                    action: 'open',
                    title: window.i18n?.js_notif_open_chat || 'Открыть чат'
                },
                {
                    action: 'close',
                    title: window.i18n?.js_notif_close || 'Закрыть'
                }
            ]
        };
        
        await this.showNotification(title, options);
    }
    
    /**
     * Получить ID пользователя (из auth или localStorage)
     */
    getUserId() {
        // Проверяем chatManager если доступен
        if (window.chatManager && window.chatManager.userId) {
            return window.chatManager.userId;
        }
        
        // Fallback to localStorage (правильный ключ для анонимных)
        return localStorage.getItem('userId') || localStorage.getItem('anonymous_user_id');
    }
    
    /**
     * Конвертировать base64 строку в Uint8Array для VAPID key
     */
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
    
    /**
     * Проверить, поддерживаются ли уведомления
     */
    isNotificationSupported() {
        return this.isSupported;
    }
    
    /**
     * Получить статус разрешения
     */
    getPermission() {
        return this.permission;
    }
    
    /**
     * Проверить, включены ли уведомления
     */
    isEnabled() {
        return this.isSupported && this.permission === 'granted' && this.subscription !== null;
    }
    
    /**
     * Получить статус подписки
     */
    getSubscriptionStatus() {
        return {
            supported: this.isSupported,
            permission: this.permission,
            subscribed: this.subscription !== null,
            ready: this.isEnabled()
        };
    }
}

// Создаем глобальный экземпляр
window.notificationManager = new NotificationManager();
