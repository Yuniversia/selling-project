/**
 * Admin Panel API Integration
 * Интегрирует админ-панель с микросервисами
 */

const AdminAPI = {
    baseURL: '/api/v1',
    
    // ===== REPORTS API =====
    reports: {
        /**
         * Получить все жалобы с фильтрацией
         * @param {Object} filters - фильтры {status, reason, post_id, limit, offset}
         * @returns {Promise}
         */
        async getAll(filters = {}) {
            const params = new URLSearchParams();
            if (filters.status) params.append('status', filters.status);
            if (filters.reason) params.append('reason', filters.reason);
            if (filters.post_id) params.append('post_id', filters.post_id);
            params.append('limit', filters.limit || 50);
            params.append('offset', filters.offset || 0);
            
            try {
                const response = await fetch(`${AdminAPI.baseURL}/reports?${params}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching reports:', error);
                throw error;
            }
        },
        
        /**
         * Получить деталь конкретной жалобы
         * @param {number} reportId
         * @returns {Promise}
         */
        async getById(reportId) {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/reports/${reportId}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error fetching report ${reportId}:`, error);
                throw error;
            }
        },
        
        /**
         * Одобрить жалобу (инициирует возврат денег)
         * @param {number} reportId
         * @param {Object} data - {admin_notes, checked_by}
         * @returns {Promise}
         */
        async approve(reportId, data = {}) {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/reports/${reportId}`, {
                    method: 'PATCH',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        status: 'approved',
                        action: data.action || null
                    })
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error approving report ${reportId}:`, error);
                throw error;
            }
        },
        
        /**
         * Отклонить жалобу
         * @param {number} reportId
         * @param {Object} data - {admin_notes, reason}
         * @returns {Promise}
         */
        async reject(reportId, data = {}) {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/reports/${reportId}`, {
                    method: 'PATCH',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        status: 'rejected',
                        action: data.action || null
                    })
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error rejecting report ${reportId}:`, error);
                throw error;
            }
        }
    },
    
    // ===== CHATS API =====
    chats: {
        /**
         * Получить список чатов для администратора
         * @param {Object} filters - {limit, offset, unread_only}
         * @returns {Promise}
         */
        async getAll(filters = {}) {
            const params = new URLSearchParams();
            params.append('limit', filters.limit || 50);
            params.append('offset', filters.offset || 0);
            if (filters.unread_only) params.append('unread_only', true);
            
            try {
                const response = await fetch(`${AdminAPI.baseURL}/chat/admin/chats?${params}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching chats:', error);
                throw error;
            }
        },
        
        /**
         * Получить сообщения чата
         * @param {number} chatId
         * @param {Object} filters - {limit, offset}
         * @returns {Promise}
         */
        async getMessages(chatId, filters = {}) {
            const params = new URLSearchParams();
            params.append('limit', filters.limit || 50);
            params.append('offset', filters.offset || 0);
            
            try {
                const response = await fetch(`${AdminAPI.baseURL}/chat/admin/chats/${chatId}/messages?${params}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error fetching chat ${chatId} messages:`, error);
                throw error;
            }
        },
        
        /**
         * Отправить сообщение в чат от администратора
         * @param {number} chatId
         * @param {Object} messageData - {message_text, file_url?, file_name?}
         * @returns {Promise}
         */
        async sendMessage(chatId, messageData) {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/chat/chats/${chatId}/messages`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        message_text: messageData.message_text,
                        message_type: messageData.message_type || 'text',
                        file_url: messageData.file_url,
                        file_name: messageData.file_name,
                        sender_id: 'admin',
                        sender_is_registered: true
                    })
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error sending message to chat ${chatId}:`, error);
                throw error;
            }
        },
        
        /**
         * Присоединиться к чату как администратор (для помощи)
         * @param {number} chatId
         * @returns {Promise}
         */
        async joinAsAdmin(chatId) {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/chat/admin/chats/${chatId}/join`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error joining chat ${chatId}:`, error);
                throw error;
            }
        }
    },
    
    // ===== PAYMENTS API (for refunds) =====
    payments: {
        /**
         * Произвести возврат по платежу
         * @param {number} paymentId
         * @param {Object} refundData - {amount_cents?, reason, admin_notes}
         * @returns {Promise}
         */
        async refund(paymentId, refundData = {}) {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/payments/admin/${paymentId}/refund`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        amount_cents: refundData.amount_cents,
                        reason: refundData.reason || 'admin_resolved_dispute',
                        admin_notes: refundData.admin_notes || 'Возврат по решению администратора'
                    })
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error(`Error refunding payment ${paymentId}:`, error);
                throw error;
            }
        },
        
        /**
         * Получить информацию о балансе сервисов платежей
         * @returns {Promise}
         */
        async getBalance() {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/payments/admin/balance`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching payment balance:', error);
                throw error;
            }
        }
    },
    
    // ===== ANALYTICS API =====
    analytics: {
        /**
         * Получить общую статистику
         * @returns {Promise}
         */
        async getDashboard() {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/analytics/admin/dashboard`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching analytics dashboard:', error);
                throw error;
            }
        },
        
        /**
         * Получить посещения сайта
         * @param {Object} filters - {period: '24h|7d|30d'}
         * @returns {Promise}
         */
        async getVisits(filters = {}) {
            const params = new URLSearchParams();
            params.append('period', filters.period || '24h');
            
            try {
                const response = await fetch(`${AdminAPI.baseURL}/analytics/admin/visits?${params}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching visits analytics:', error);
                throw error;
            }
        },
        
        /**
         * Получить информацию о заказах
         * @param {Object} filters - {status, period}
         * @returns {Promise}
         */
        async getOrders(filters = {}) {
            const params = new URLSearchParams();
            if (filters.status) params.append('status', filters.status);
            params.append('period', filters.period || '24h');
            
            try {
                const response = await fetch(`${AdminAPI.baseURL}/analytics/admin/orders?${params}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error fetching orders analytics:', error);
                throw error;
            }
        }
    },
    
    // ===== EXTERNAL SERVICES HEALTH =====
    services: {
        /**
         * Получить баланс внешних сервисов
         * @returns {Promise}
         */
        async getBalance() {
            try {
                const [imeiResponse, smsResponse] = await Promise.all([
                    fetch(`${AdminAPI.baseURL}/imei/balance`, {
                        method: 'GET',
                        credentials: 'include',
                        headers: { 'Accept': 'application/json' }
                    }),
                    fetch(`${AdminAPI.baseURL}/notifications/balance`, {
                        method: 'GET',
                        credentials: 'include',
                        headers: { 'Accept': 'application/json' }
                    })
                ]);

                if (!imeiResponse.ok) throw new Error(`IMEI HTTP ${imeiResponse.status}`);
                if (!smsResponse.ok) throw new Error(`SMS HTTP ${smsResponse.status}`);

                const imei = await imeiResponse.json();
                const sms = await smsResponse.json();

                return {
                    status: 'success',
                    data: {
                        imei_service: imei?.data || null,
                        sms_service: sms?.data || null,
                    }
                };
            } catch (error) {
                console.error('Error fetching services balance:', error);
                throw error;
            }
        },
        
        /**
         * Проверить здоровье всех сервисов
         * @returns {Promise}
         */
        async healthCheck() {
            try {
                const response = await fetch(`${AdminAPI.baseURL}/admin/services/health`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('Error checking services health:', error);
                throw error;
            }
        }
    }
};

/**
 * Helper Functions for Admin Panel
 */
const AdminHelper = {
    /**
     * Форматировать дату
     */
    formatDate(date) {
        return new Date(date).toLocaleDateString('ru-RU', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    /**
     * Форматировать время как "X часов назад"
     */
    formatTimeAgo(date) {
        const seconds = Math.floor((new Date() - new Date(date)) / 1000);
        
        if (seconds < 60) return 'Только что';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}м назад`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}ч назад`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}д назад`;
        
        return AdminHelper.formatDate(date);
    },
    
    /**
     * Форматировать сумму денег
     */
    formatMoney(cents, currency = 'eur') {
        const amount = (cents / 100).toFixed(2);
        const symbols = {
            'eur': '€',
            'usd': '$',
            'gbp': '£'
        };
        return `${symbols[currency] || currency}${amount}`;
    },
    
    /**
     * Показать уведомление
     */
    notify(message, type = 'success', duration = 3000) {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 20px;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#06b6d4'};
            color: white;
            border-radius: 8px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            z-index: 10000;
            animation: slideIn 0.3s;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    },
    
    /**
     * Проверить доступ администратора
     */
    checkAdminAccess() {
        try {
            const token = document.cookie
                .split('; ')
                .find(row => row.startsWith('access_token='))
                ?.split('=')[1];
            
            if (!token) return false;
            
            // Decode JWT (basic, without verification)
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.user_type === 'admin';
        } catch (e) {
            return false;
        }
    }
};

// Экспортируем API для использования в админ-панели
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AdminAPI, AdminHelper };
}
