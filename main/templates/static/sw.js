// Service Worker для Push-уведомлений
const CACHE_NAME = 'lais-chat-v1';

self.addEventListener('install', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_installed || 'Service Worker установлен'));
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_activated || 'Service Worker активирован'));
    event.waitUntil(clients.claim());
});

// Обработка push-уведомлений
self.addEventListener('push', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_push_received || 'Push-уведомление получено'));
    
    let data = {};
    
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = {
                title: self.i18n?.js_notif_new_message || 'Новое сообщение',
                body: event.data.text(),
                icon: '/static/icon-192.png',
                badge: '/static/badge-72.png'
            };
        }
    }
    
    const options = {
        body: data.body || (self.i18n?.js_notif_default_body || 'У вас новое сообщение в чате'),
        icon: data.icon || '/static/icon-192.png',
        badge: data.badge || '/static/badge-72.png',
        vibrate: [200, 100, 200],
        tag: data.tag || 'chat-message',
        data: {
            url: data.url || '/',
            chatId: data.chatId
        },
        actions: [
            {
                action: 'open',
                title: self.i18n?.js_sw_open || 'Открыть',
                icon: '/static/open-icon.png'
            },
            {
                action: 'close',
                title: self.i18n?.js_notif_close || 'Закрыть',
                icon: '/static/close-icon.png'
            }
        ],
        requireInteraction: false,
        renotify: true
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || (self.i18n?.js_notif_new_message || 'Новое сообщение'), options)
    );
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_notification_click || 'Клик по уведомлению:'), event.action);
    
    event.notification.close();
    
    if (event.action === 'close') {
        return;
    }
    
    // Открываем чат
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                const url = event.notification.data.url || '/';
                
                // Проверяем, есть ли уже открытое окно
                for (let client of clientList) {
                    if (client.url === url && 'focus' in client) {
                        return client.focus();
                    }
                }
                
                // Открываем новое окно
                if (clients.openWindow) {
                    return clients.openWindow(url);
                }
            })
    );
});

// Обработка закрытия уведомлений
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_notification_closed || 'Уведомление закрыто:'), event.notification.tag);
});
