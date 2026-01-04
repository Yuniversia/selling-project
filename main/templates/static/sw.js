// Service Worker для Push-уведомлений
const CACHE_NAME = 'lais-chat-v36';  // Updated for modal fixes

self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker установлен');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker активирован');
    event.waitUntil(
        clients.claim().then(() => {
            console.log('[SW] Все клиенты под контролем SW');
        })
    );
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
                icon: '/templates/static/icon-192.png.svg',
                badge: '/templates/static/badge-72.png.svg'
            };
        }
    }
    
    const options = {
        body: data.body || 'У вас новое сообщение в чате',
        icon: data.icon || '/templates/static/icon-192.png.svg',
        badge: data.badge || '/templates/static/badge-72.png.svg',
        vibrate: [200, 100, 200],
        tag: data.tag || 'chat-message',
        renotify: true,
        requireInteraction: false,
        silent: false,
        sound: '/templates/static/sounds/notification.mp3',
        data: {
            url: data.url || '/profile',
            chatId: data.chatId
        },
        actions: [
            {
                action: 'open',
                title: 'Открыть',
                icon: '/templates/static/open-icon.png'
            },
            {
                action: 'close',
                title: 'Закрыть',
                icon: '/templates/static/close-icon.png'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || (self.i18n?.js_notif_new_message || 'Новое сообщение'), options)
    );
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_notification_click || 'Клик по уведомлению:'), event.action);
    console.log('[SW] Notification data:', event.notification.data);
    
    event.notification.close();
    
    if (event.action === 'close') {
        return;
    }
    
    // Determine URL based on user type
    const data = event.notification.data || {};
    let targetUrl = '/profile';  // Default for registered users
    
    console.log('[SW] Data analysis:', {
        buyer_is_registered: data.buyer_is_registered,
        iphone_id: data.iphone_id,
        chatId: data.chatId
    });
    
    // If buyer is anonymous (not registered), open product page
    if (data.buyer_is_registered === false && data.iphone_id) {
        targetUrl = `/product?id=${data.iphone_id}`;
        console.log('[SW] Opening product page for anonymous user:', targetUrl);
    } else if (data.iphone_id && !data.buyer_is_registered) {
        // Fallback if buyer_is_registered is undefined but we have iphone_id
        targetUrl = `/product?id=${data.iphone_id}`;
        console.log('[SW] Opening product page (fallback):', targetUrl);
    } else {
        console.log('[SW] Opening profile page for registered user:', targetUrl);
    }
    
    // Открываем чат
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Проверяем, есть ли уже открытое окно с этим URL
                for (let client of clientList) {
                    const clientPath = new URL(client.url).pathname;
                    const targetPath = new URL(targetUrl, self.location.origin).pathname;
                    
                    if (clientPath === targetPath && 'focus' in client) {
                        console.log('[SW] Found existing window, focusing');
                        return client.focus().then(client => {
                            // Отправляем сообщение для открытия чата
                            if (data.chatId) {
                                client.postMessage({
                                    type: 'OPEN_CHAT',
                                    chatId: data.chatId
                                });
                            }
                            return client;
                        });
                    }
                }
                
                // Открываем новое окно
                if (clients.openWindow) {
                    console.log('[SW] Opening new window:', targetUrl);
                    return clients.openWindow(targetUrl).then(client => {
                        // После открытия окна отправляем сообщение для открытия чата
                        if (client && data.chatId) {
                            // Даем странице время загрузиться
                            setTimeout(() => {
                                client.postMessage({
                                    type: 'OPEN_CHAT',
                                    chatId: data.chatId
                                });
                            }, 1500);
                        }
                        return client;
                    });
                }
            })
    );
});

// Обработка закрытия уведомлений
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] ' + (self.i18n?.js_sw_notification_closed || 'Уведомление закрыто:'), event.notification.tag);
});
