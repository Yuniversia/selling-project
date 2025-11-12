document.addEventListener('DOMContentLoaded', () => {
    // -----------------------------------------------------------------
    // 1. Логика Модального окна Авторизации/Регистрации (Главная и Продукт)
    // -----------------------------------------------------------------
    const loginBtn = document.getElementById('login-btn');
    const modal = document.getElementById('auth-modal');
    const closeModal = document.querySelector('.close-btn');
    const loginTab = document.getElementById('login-tab');
    const registerTab = document.getElementById('register-tab');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');

    if (modal) {
        // Открытие модального окна
        loginBtn && loginBtn.addEventListener('click', () => {
            modal.style.display = 'block';
        });

        // Закрытие по крестику
        closeModal && closeModal.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // Закрытие по клику вне окна
        window.addEventListener('click', (event) => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Переключение вкладок
        loginTab && loginTab.addEventListener('click', () => {
            loginTab.classList.add('active');
            registerTab.classList.remove('active');
            loginForm.classList.add('active-form');
            registerForm.classList.remove('active-form');
        });

        registerTab && registerTab.addEventListener('click', () => {
            registerTab.classList.add('active');
            loginTab.classList.remove('active');
            registerForm.classList.add('active-form');
            loginForm.classList.remove('active-form');
        });
    }

    // -----------------------------------------------------------------
    // 3. Имитация Бесконечной ленты (Главная страница)
    // -----------------------------------------------------------------
    const productFeed = document.getElementById('product-feed');
    // Обновленная палитра для фона карточек
    const colors = ['#26a33c', '#007db9', '#3c26a3', '#a1005d', '#a33c26']; 

    // Функция для создания новой карточки
    function createProductCard(price, title, location) {
        const randomColor = colors[Math.floor(Math.random() * colors.length)];
        const card = document.createElement('a');
        card.href = 'product.html';
        card.classList.add('product-card');
        card.innerHTML = `
            <div class="image-placeholder" style="background-color: ${randomColor};">
                <span class="price-overlay">${price}</span>
            </div>
            <div class="card-info">
                <h3 class="title">${title}</h3>
                <div class="card-footer">
                    <span class="location"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${location}</span>
                    <span class="like-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></span>
                </div>
            </div>
        `;
        return card;
    }

    // Загрузка новых товаров при прокрутке
    let loading = false;
    const scrollHandler = () => {
        if (loading || !productFeed) return;

        // Расчет прокрутки
        const scrollThreshold = document.documentElement.scrollHeight - window.innerHeight - 800;
        
        if (window.scrollY >= scrollThreshold) {
            loading = true;
            // Имитация задержки загрузки
            setTimeout(() => {
                const cities = ['Тарту, EE', 'Вентспилс, LV', 'Клайпеда, LT', 'Пярну, EE', 'Даугавпилс, LV'];
                const titles = [
                    'Фотоаппарат Pro (б/у)', 
                    'Сервер Dell R720', 
                    'Услуги электрика (Тариф Comfort)', 
                    'Рабочий стол IKEA',
                    'Спортивный велосипед горный',
                    'Старинный граммофон'
                ];
                
                for (let i = 0; i < 8; i++) {
                    const randomPrice = (Math.floor(Math.random() * 900) + 10) * 10;
                    const newCard = createProductCard(
                        `€${randomPrice}`,
                        titles[Math.floor(Math.random() * titles.length)],
                        cities[Math.floor(Math.random() * cities.length)]
                    );
                    productFeed.appendChild(newCard);
                }
                loading = false;
            }, 500);
        }
    };

    if (productFeed) {
        // Добавление нескольких элементов для начала прокрутки (сверх тех, что в HTML)
        for (let i = 0; i < 8; i++) {
             const randomPrice = (Math.floor(Math.random() * 900) + 10) * 10;
             const cities = ['Тарту, EE', 'Вентспилс, LV', 'Клайпеда, LT', 'Пярну, EE', 'Даугавпилс, LV'];
             productFeed.appendChild(createProductCard(
                `€${randomPrice}`,
                'Дополнительный товар #' + (i + 1) + ' для прокрутки',
                cities[Math.floor(Math.random() * cities.length)]
            ));
        }
        window.addEventListener('scroll', scrollHandler);
    }
});