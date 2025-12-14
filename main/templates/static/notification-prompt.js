// Автоматический запрос разрешения на уведомления
(function() {
    // Проверяем, запрашивали ли мы уже разрешение
    const hasAsked = localStorage.getItem('notification_permission_asked');
    
    if (!hasAsked && window.notificationManager) {
        // Ждем загрузки страницы и небольшую задержку для лучшего UX
        setTimeout(() => {
            // Проверяем статус
            if (window.notificationManager.getPermission() === 'default') {
                // Показываем дружелюбное уведомление
                const shouldAsk = confirm(
                    (window.i18n?.js_notif_prompt_title || 'Хотите получать уведомления о новых сообщениях в чате?') + '\n\n' +
                    (window.i18n?.js_notif_prompt_description || 'Это поможет вам не пропустить важные сообщения от покупателей/продавцов.')
                );
                
                if (shouldAsk) {
                    window.notificationManager.requestPermission().then(granted => {
                        if (granted) {
                            console.log('[App] ' + (window.i18n?.js_notif_enabled || 'Уведомления включены'));
                        }
                    });
                }
                
                // Отмечаем что мы спросили
                localStorage.setItem('notification_permission_asked', 'true');
            }
        }, 3000); // Задержка 3 секунды после загрузки
    }
})();
