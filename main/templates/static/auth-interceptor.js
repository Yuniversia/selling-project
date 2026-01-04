/**
 * Auth Refresh Interceptor
 * Автоматически обновляет токен при ошибке 401
 */

(function() {
    const originalFetch = window.fetch;
    let isRefreshing = false;
    let refreshSubscribers = [];

    function subscribeTokenRefresh(cb) {
        refreshSubscribers.push(cb);
    }

    function onRefreshed() {
        refreshSubscribers.forEach(cb => cb());
        refreshSubscribers = [];
    }

    async function refreshToken() {
        if (isRefreshing) {
            return new Promise((resolve) => {
                subscribeTokenRefresh(resolve);
            });
        }

        isRefreshing = true;
        console.log('[AuthInterceptor] Refreshing token...');

        try {
            const response = await originalFetch('/api/v1/auth/refresh', {
                method: 'POST',
                credentials: 'include'
            });

            if (response.ok) {
                console.log('[AuthInterceptor] Token refreshed successfully');
                isRefreshing = false;
                onRefreshed();
                return true;
            } else {
                console.error('[AuthInterceptor] Refresh failed:', response.status);
                isRefreshing = false;
                // Redirect to home if refresh fails
                window.location.href = '/';
                return false;
            }
        } catch (error) {
            console.error('[AuthInterceptor] Refresh error:', error);
            isRefreshing = false;
            window.location.href = '/';
            return false;
        }
    }

    window.fetch = async function(...args) {
        const response = await originalFetch.apply(this, args);

        // Если получили 401 и это не сам запрос на refresh
        if (response.status === 401 && !args[0].includes('/auth/refresh')) {
            // Проверяем, это запрос к /me (проверка авторизации)
            if (args[0].includes('/auth/me')) {
                // Это нормально для неавторизованных - не редиректим
                console.log('[AuthInterceptor] User not authenticated (expected for guests)');
                return response;
            }
            
            console.log('[AuthInterceptor] Got 401, attempting refresh');
            
            const refreshed = await refreshToken();
            
            if (refreshed) {
                // Повторяем исходный запрос
                console.log('[AuthInterceptor] Retrying original request');
                return await originalFetch.apply(this, args);
            }
        }

        return response;
    };

    console.log('[AuthInterceptor] Initialized');
})();
