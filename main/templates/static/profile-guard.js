(function () {
    'use strict';

    function getLangCookie() {
        const m = document.cookie.match(/(?:^|;\s*)lang=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : null;
    }

    async function checkProfile() {
        let user;
        try {
            const res = await fetch('/api/v1/auth/me', { credentials: 'include' });
            if (!res.ok) return;
            user = await res.json();
        } catch (_) { return; }

        // Language is OK if stored in DB OR already set via lang cookie
        const missingPhone = !user.phone;
        const missingLang  = !user.preferred_language && !getLangCookie();

        if (!missingPhone && !missingLang) return;
        if (document.getElementById('profile-guard-overlay')) return;
        showModal(user, missingPhone, missingLang);
    }

    function showModal(user, needsPhone, needsLang) {
        const overlay = document.createElement('div');
        overlay.id = 'profile-guard-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:99999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);';

        const card = document.createElement('div');
        card.style.cssText = 'background:#fff;border-radius:20px;padding:36px 32px;max-width:420px;width:92%;box-shadow:0 24px 64px rgba(0,0,0,.25);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-sizing:border-box;';

        const phoneFld = needsPhone ? `
          <div style="margin-bottom:18px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#444;margin-bottom:6px;">Phone number</label>
            <input id="pg-phone" type="tel" placeholder="+371 2x xxx xxx"
              style="width:100%;padding:12px 14px;font-size:15px;border:1.5px solid #d5d5d5;border-radius:10px;outline:none;box-sizing:border-box;"
              value="${user.phone || ''}">
          </div>` : '';

        const langFld = needsLang ? `
          <div style="margin-bottom:18px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#444;margin-bottom:6px;">Language / Valoda</label>
            <select id="pg-lang" style="width:100%;padding:12px 14px;font-size:15px;border:1.5px solid #d5d5d5;border-radius:10px;outline:none;box-sizing:border-box;background:#fff;cursor:pointer;-webkit-appearance:none;appearance:none;">
              <option value="">-- Select --</option>
              <option value="lv">Latviski</option>
              <option value="ru">Russki</option>
              <option value="en">English</option>
            </select>
          </div>` : '';

        card.innerHTML = `
          <div style="text-align:center;margin-bottom:24px;">
            <div style="width:52px;height:52px;background:#eef5ff;border-radius:14px;margin:0 auto 14px;display:flex;align-items:center;justify-content:center;">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#007AFF" stroke-width="2.2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
            <h2 style="font-size:20px;font-weight:700;margin:0 0 6px;color:#111;">Complete your profile</h2>
            <p style="font-size:13px;color:#888;margin:0;line-height:1.5;">Please fill in the required details to use the platform</p>
          </div>
          ${phoneFld}
          ${langFld}
          <p id="pg-err" style="display:none;color:#d32f2f;font-size:13px;margin:-8px 0 12px;padding:8px 12px;background:#fdecea;border-radius:8px;"></p>
          <button id="pg-save" style="width:100%;background:#007AFF;color:#fff;border:none;border-radius:12px;padding:14px;font-size:16px;font-weight:600;cursor:pointer;">Save and continue</button>
        `;

        overlay.appendChild(card);
        document.body.appendChild(overlay);

        if (!document.getElementById('pg-style')) {
            const s = document.createElement('style');
            s.id = 'pg-style';
            s.textContent = '@keyframes pgShake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-6px)}40%,80%{transform:translateX(6px)}}';
            document.head.appendChild(s);
        }

        overlay.addEventListener('click', e => {
            if (e.target !== overlay) return;
            card.style.animation = 'none';
            void card.offsetHeight;
            card.style.animation = 'pgShake .35s ease';
        });

        document.getElementById('pg-save').addEventListener('click', async () => {
            const phoneEl = document.getElementById('pg-phone');
            const langEl  = document.getElementById('pg-lang');
            const errEl   = document.getElementById('pg-err');
            const btn     = document.getElementById('pg-save');

            const phone = phoneEl ? phoneEl.value.trim() : null;
            const lang  = langEl  ? langEl.value        : null;

            // --- Client-side validation ---
            if (needsPhone && (!phone || phone.replace(/\D/g, '').length < 7)) {
                errEl.textContent = 'Please enter a valid phone number';
                errEl.style.display = 'block';
                return;
            }
            if (needsLang && !lang) {
                errEl.textContent = 'Please select a language';
                errEl.style.display = 'block';
                return;
            }

            errEl.style.display = 'none';
            btn.disabled = true;
            btn.textContent = 'Saving...';

            // Apply language cookie immediately so re-check after reload won't re-show the popup
            if (lang) {
                document.cookie = 'lang=' + lang + ';path=/;max-age=31536000;samesite=lax';
                try { await fetch('/set-language/' + lang, { credentials: 'include' }); } catch (_) {}
            }

            const body = {};
            if (phone) body.phone = phone;
            if (lang)  body.preferred_language = lang;

            try {
                const res = await fetch('/api/v1/auth/me', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(body),
                });

                if (res.ok || res.status >= 500) {
                    // On success OR server error: language cookie is already set above,
                    // so the guard won't re-trigger on reload.
                    overlay.remove();
                    window.location.reload();
                } else {
                    // 400/422 - real validation error from server
                    const d = await res.json().catch(() => ({}));
                    const msg = (d.errors && (d.errors.phone || d.errors.email)) || d.message || 'Error saving profile';
                    errEl.textContent = msg;
                    errEl.style.display = 'block';
                    btn.disabled = false;
                    btn.textContent = 'Save and continue';
                }
            } catch (_) {
                // Network error - still close if language was already applied
                if (lang) {
                    overlay.remove();
                    window.location.reload();
                } else {
                    errEl.textContent = 'Connection error. Please try again.';
                    errEl.style.display = 'block';
                    btn.disabled = false;
                    btn.textContent = 'Save and continue';
                }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkProfile);
    } else {
        checkProfile();
    }
})();