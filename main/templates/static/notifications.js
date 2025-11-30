/**
 * Push Notifications Manager
 * Управление Web Push уведомлениями
 */

class NotificationManager {
    constructor() {
        this.swRegistration = null;
        this.isSupported = 'Notification' in window && 'serviceWorker' in navigator;
        this.permission = this.isSupported ? Notification.permission : 'denied';
        
        if (this.isSupported) {
            this.init();
        } else {
            console.warn('[Notifications] Push-уведомления не поддерживаются браузером');
        }
    }
    
    async init() {
        try {
            // Регистрируем Service Worker
            this.swRegistration = await navigator.serviceWorker.register('/sw.js', {
                scope: '/'
            });
            
            console.log('[Notifications] Service Worker зарегистрирован:', this.swRegistration.scope);
            
            // Ждем активации
            await navigator.serviceWorker.ready;
            console.log('[Notifications] Service Worker активен');
            
            // Проверяем текущее разрешение
            this.permission = Notification.permission;
            
        } catch (error) {
            console.error('[Notifications] Ошибка регистрации Service Worker:', error);
        }
    }
    
    /**
     * Запросить разрешение на уведомления
     */
    async requestPermission() {
        if (!this.isSupported) {
            console.warn('[Notifications] Push-уведомления не поддерживаются');
            return false;
        }
        
        if (this.permission === 'granted') {
            console.log('[Notifications] Разрешение уже получено');
            return true;
        }
        
        try {
            const permission = await Notification.requestPermission();
            this.permission = permission;
            
            if (permission === 'granted') {
                console.log('[Notifications] Разрешение на уведомления получено');
                return true;
            } else {
                console.log('[Notifications] Разрешение на уведомления отклонено');
                return false;
            }
        } catch (error) {
            console.error('[Notifications] Ошибка запроса разрешения:', error);
            return false;
        }
    }
    
    /**
     * Показать локальное уведомление (не через push)
     */
    async showNotification(title, options = {}) {
        if (!this.isSupported || this.permission !== 'granted') {
            console.warn('[Notifications] Нет разрешения на уведомления');
            return;
        }
        
        try {
            const defaultOptions = {
                body: 'У вас новое сообщение',
                icon: '/static/icon-192.png',
                badge: '/static/badge-72.png',
                vibrate: [200, 100, 200],
                tag: 'chat-message',
                requireInteraction: false,
                renotify: true,
                silent: false
            };
            
            const notificationOptions = { ...defaultOptions, ...options };
            
            if (this.swRegistration) {
                // Показываем через Service Worker
                await this.swRegistration.showNotification(title, notificationOptions);
            } else {
                // Fallback - показываем напрямую
                new Notification(title, notificationOptions);
            }
            
            console.log('[Notifications] Уведомление показано:', title);
        } catch (error) {
            console.error('[Notifications] Ошибка показа уведомления:', error);
        }
    }
    
    /**
     * Показать уведомление о новом сообщении в чате
     */
    async notifyNewMessage(senderName, messageText, chatId) {
        if (!this.isSupported || this.permission !== 'granted') {
            return;
        }
        
        // Не показываем уведомление если окно активно
        if (document.visibilityState === 'visible' && document.hasFocus()) {
            console.log('[Notifications] Окно активно, уведомление не показано');
            return;
        }
        
        const title = `Новое сообщение от ${senderName}`;
        const options = {
            body: messageText.length > 100 ? messageText.substring(0, 100) + '...' : messageText,
            icon: '/static/icon-192.png',
            badge: '/static/badge-72.png',
            tag: `chat-${chatId}`,
            data: {
                chatId: chatId,
                url: window.location.origin + '/profile'
            },
            actions: [
                {
                    action: 'open',
                    title: 'Открыть чат'
                },
                {
                    action: 'close',
                    title: 'Закрыть'
                }
            ]
        };
        
        await this.showNotification(title, options);
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
        return this.isSupported && this.permission === 'granted';
    }
}

// Создаем глобальный экземпляр
window.notificationManager = new NotificationManager();
