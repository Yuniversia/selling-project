/**
 * Push Notifications Initializer
 * Lightweight script to register Service Worker and handle push subscriptions
 * Should be included on ALL pages
 */

(async function() {
    'use strict';
    
    // Check if push notifications are supported
    if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.log('[Push Init] Push notifications not supported');
        return;
    }
    
    try {
        // Register Service Worker
        const registration = await navigator.serviceWorker.register('/templates/static/sw.js', {
            scope: '/'
        });
        
        console.log('[Push Init] Service Worker registered:', registration.scope);
        
        // Wait for SW to be ready
        await navigator.serviceWorker.ready;
        console.log('[Push Init] Service Worker ready');
        
        // Check if user already granted permission
        if (Notification.permission === 'granted') {
            // Get user ID if logged in
            const userId = await getCurrentUserId();
            if (!userId) {
                console.log('[Push Init] User not logged in, skipping auto-subscribe');
                return;
            }
            
            // Check if we already have a subscription
            const existingSubscription = await registration.pushManager.getSubscription();
            
            if (existingSubscription) {
                console.log('[Push Init] Push subscription exists, re-saving to server');
                // ALWAYS save to server even if subscription exists
                // This ensures DB has the subscription
                await saveSubscriptionToServer(userId, existingSubscription);
                return;
            }
            
            // Auto-subscribe if permission granted but no subscription
            console.log('[Push Init] Auto-subscribing to push notifications');
            await subscribeToPush(registration, userId);
        }
        
    } catch (error) {
        console.error('[Push Init] Error:', error);
    }
})();

/**
 * Get current user ID from cookies or API
 */
async function getCurrentUserId() {
    try {
        // Try to get from /api/v1/auth/me
        const response = await fetch('/api/v1/auth/me', {
            credentials: 'include'
        });
        
        if (response.ok) {
            const user = await response.json();
            return user.id ? String(user.id) : null;
        }
    } catch (error) {
        console.log('[Push Init] Could not get user ID:', error.message);
    }
    
    return null;
}

/**
 * Subscribe to push notifications
 */
async function subscribeToPush(registration, userId) {
    try {
        // Get VAPID public key
        const keyResponse = await fetch('/api/v1/chat/push/vapid-public-key');
        if (!keyResponse.ok) {
            console.error('[Push Init] Could not get VAPID key');
            return;
        }
        
        const { publicKey } = await keyResponse.json();
        const applicationServerKey = urlBase64ToUint8Array(publicKey);
        
        // Subscribe
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        });
        
        console.log('[Push Init] Push subscription created');
        
        // Save to server
        await saveSubscriptionToServer(userId, subscription);
        
    } catch (error) {
        console.error('[Push Init] Error subscribing:', error);
    }
}

/**
 * Save subscription to server
 */
async function saveSubscriptionToServer(userId, subscription) {
    try {
        const saveResponse = await fetch(`/api/v1/chat/push/subscribe?user_id=${userId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(subscription.toJSON())
        });
        
        if (saveResponse.ok) {
            console.log('[Push Init] ✅ Push subscription saved for user:', userId);
        } else {
            const errorText = await saveResponse.text();
            console.error('[Push Init] ❌ Failed to save subscription:', saveResponse.status, errorText);
        }
    } catch (error) {
        console.error('[Push Init] ❌ Error saving subscription:', error);
    }
}

/**
 * Convert VAPID key from base64 to Uint8Array
 */
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');
    
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    
    return outputArray;
}

// Expose function to manually request permission (for use in UI)
window.requestPushPermission = async function() {
    if (!('Notification' in window)) {
        alert('Push notifications are not supported in this browser');
        return false;
    }
    
    const permission = await Notification.requestPermission();
    
    if (permission === 'granted') {
        const userId = await getCurrentUserId();
        if (userId) {
            const registration = await navigator.serviceWorker.ready;
            await subscribeToPush(registration, userId);
            return true;
        }
    }
    
    return false;
};
