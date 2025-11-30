/**
 * Cache Manager
 * Управление кешированием API запросов для снижения нагрузки на сервер
 */

class CacheManager {
    constructor() {
        this.cache = new Map();
        this.defaultTTL = 5 * 60 * 1000; // 5 минут по умолчанию
    }

    /**
     * Получить данные из кеша
     * @param {string} key - Ключ кеша
     * @returns {any|null} - Данные или null если кеш истек/не найден
     */
    get(key) {
        const cached = this.cache.get(key);
        
        if (!cached) {
            return null;
        }
        
        const now = Date.now();
        if (now > cached.expires) {
            // Кеш истек
            this.cache.delete(key);
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
        const expires = Date.now() + ttl;
        this.cache.set(key, { data, expires });
        console.log(`[Cache] SET: ${key} (TTL: ${ttl/1000}s)`);
    }

    /**
     * Очистить кеш по ключу
     * @param {string} key - Ключ кеша
     */
    delete(key) {
        this.cache.delete(key);
        console.log(`[Cache] DELETE: ${key}`);
    }

    /**
     * Очистить весь кеш
     */
    clear() {
        this.cache.clear();
        console.log('[Cache] CLEAR: Весь кеш очищен');
    }

    /**
     * Получить размер кеша
     */
    size() {
        return this.cache.size;
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
