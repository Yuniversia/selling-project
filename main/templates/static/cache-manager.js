/**
 * Cache Manager
 * Управление кешированием API запросов для снижения нагрузки на сервер
 * Использует localStorage для сохранения между перезагрузками страницы
 */

class CacheManager {
    constructor() {
        this.storageKey = 'api_cache';
        this.defaultTTL = 5 * 60 * 1000; // 5 минут по умолчанию
        this.cleanExpired(); // Очищаем устаревшие записи при инициализации
    }

    /**
     * Получить весь кеш из localStorage
     * @returns {Object} - Объект с кешем
     */
    _getCache() {
        try {
            const cached = localStorage.getItem(this.storageKey);
            return cached ? JSON.parse(cached) : {};
        } catch (e) {
            console.error('[Cache] Ошибка чтения кеша:', e);
            return {};
        }
    }

    /**
     * Сохранить весь кеш в localStorage
     * @param {Object} cache - Объект с кешем
     */
    _saveCache(cache) {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(cache));
        } catch (e) {
            console.error('[Cache] Ошибка сохранения кеша:', e);
            // Если переполнение localStorage - очищаем старые записи
            if (e.name === 'QuotaExceededError') {
                console.warn('[Cache] localStorage переполнен, очищаем...');
                this.clear();
            }
        }
    }

    /**
     * Получить данные из кеша
     * @param {string} key - Ключ кеша
     * @returns {any|null} - Данные или null если кеш истек/не найден
     */
    get(key) {
        const cache = this._getCache();
        const cached = cache[key];
        
        if (!cached) {
            return null;
        }
        
        const now = Date.now();
        if (now > cached.expires) {
            // Кеш истек
            this.delete(key);
            return null;
        }
        
        console.log(`[Cache] HIT: ${key}`);
        return cached.data;
    }

    /**
     * Сохранить данные в кеш
     * @param {string} key - Ключ кеша
     * @param {any} data - Данные для кеширования
     * @param {number} ttl - Время жизни в миллисекундах (опционально)
     */
    set(key, data, ttl = this.defaultTTL) {
        const cache = this._getCache();
        const expires = Date.now() + ttl;
        cache[key] = { data, expires };
        this._saveCache(cache);
        console.log(`[Cache] SET: ${key} (TTL: ${ttl/1000}s)`);
    }

    /**
     * Очистить кеш по ключу
     * @param {string} key - Ключ кеша
     */
    delete(key) {
        const cache = this._getCache();
        delete cache[key];
        this._saveCache(cache);
        console.log(`[Cache] DELETE: ${key}`);
    }

    /**
     * Очистить весь кеш
     */
    clear() {
        localStorage.removeItem(this.storageKey);
        console.log('[Cache] CLEAR: Весь кеш очищен');
    }

    /**
     * Очистить только пользовательские данные из кеша
     * Сохраняет системные настройки (уведомления, cookies и т.д.)
     */
    clearUserData() {
        const cache = this._getCache();
        const userDataPatterns = [
            /^GET:.*\/auth\//,           // Данные авторизации
            /^GET:.*\/posts\//,          // Посты пользователя
            /^GET:.*\/profile/,          // Профиль
            /^GET:.*\/admin\//,          // Админ данные
            /^GET:.*\/reports/,          // Жалобы
            /^GET:.*\/messages/,         // Сообщения
            /^GET:.*\/chats/,            // Чаты
            /user/i,                     // Любые ключи с 'user'
            /profile/i                   // Любые ключи с 'profile'
        ];
        
        let cleaned = 0;
        Object.keys(cache).forEach(key => {
            // Проверяем, соответствует ли ключ паттернам пользовательских данных
            const isUserData = userDataPatterns.some(pattern => pattern.test(key));
            if (isUserData) {
                delete cache[key];
                cleaned++;
            }
        });
        
        if (cleaned > 0) {
            this._saveCache(cache);
            console.log(`[Cache] Очищено пользовательских записей: ${cleaned}`);
        }
    }

    /**
     * Очистить устаревшие записи
     */
    cleanExpired() {
        const cache = this._getCache();
        const now = Date.now();
        let cleaned = 0;
        
        Object.keys(cache).forEach(key => {
            if (now > cache[key].expires) {
                delete cache[key];
                cleaned++;
            }
        });
        
        if (cleaned > 0) {
            this._saveCache(cache);
            console.log(`[Cache] Очищено устаревших записей: ${cleaned}`);
        }
    }

    /**
     * Получить размер кеша
     */
    size() {
        return Object.keys(this._getCache()).length;
    }
}

// Создаем глобальный экземпляр
window.cacheManager = new CacheManager();

/**
 * Wrapper для fetch с автоматическим кешированием
 * @param {string} url - URL запроса
 * @param {object} options - Опции fetch
 * @param {number} cacheTTL - Время жизни кеша в миллисекундах (0 = без кеша)
 * @returns {Promise<Response>}
 */
async function cachedFetch(url, options = {}, cacheTTL = 300000) {
    // Если cacheTTL = 0, не используем кеш
    if (cacheTTL === 0) {
        return fetch(url, options);
    }

    // Генерируем ключ кеша из URL и метода
    const method = options.method || 'GET';
    const cacheKey = `${method}:${url}`;

    // Проверяем кеш только для GET запросов
    if (method === 'GET') {
        const cached = window.cacheManager.get(cacheKey);
        if (cached) {
            // Возвращаем закешированный ответ
            return new Response(JSON.stringify(cached), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }
    }

    // Выполняем запрос
    console.log(`[Cache] MISS: ${cacheKey} - Выполняем запрос...`);
    const response = await fetch(url, options);

    // Кешируем только успешные GET запросы
    if (method === 'GET' && response.ok) {
        const clone = response.clone();
        const data = await clone.json();
        window.cacheManager.set(cacheKey, data, cacheTTL);
    }

    return response;
}

// Экспортируем для использования
window.cachedFetch = cachedFetch;
