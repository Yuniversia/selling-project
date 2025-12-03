// Сохранить как: templates/static/profile.js

document.addEventListener('DOMContentLoaded', () => {
    
    const token = localStorage.getItem("access_token");

    // 1. ПРОВЕРКА АВТОРИЗАЦИИ
    if (!token) {
        // Если токена нет, немедленно перенаправляем на главную
        alert("Для доступа к профилю необходимо авторизоваться.");
        window.location.href = "/"; 
        return;
    }

    // Находим элементы на странице
    const usernameField = document.getElementById('profile-username');
    const emailField = document.getElementById('profile-email');
    const surnameField = document.getElementById('profile-surname');
    const phoneField = document.getElementById('profile-phone');
    const createdStat = document.getElementById('stat-created');
    const avatarPreview = document.getElementById('avatar-preview');
    const profileForm = document.getElementById('profile-form');

    // 2. ЗАГРУЗКА ДАННЫХ
    async function fetchProfileData() {
        try {
            // Пытаемся получить данные с защищенного эндпоинта
            const response = await fetch("/api/v1/auth/me", {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });

            if (!response.ok) {
                // Если токен есть, но он недействителен (например, истек)
                if (response.status === 401) {
                    localStorage.removeItem("access_token"); // Чистим неверный токен
                    alert("Ваша сессия истекла. Пожалуйста, войдите снова.");
                    window.location.href = "/";
                }
                throw new Error(`Ошибка: ${response.statusText}`);
            }

            const user = await response.json();
            
            // 3. ЗАПОЛНЕНИЕ ПОЛЕЙ
            // Данные из БД (модель User)
            usernameField.value = user.username;
            emailField.value = user.email;
            
            // Первые 2 буквы для аватара
            avatarPreview.textContent = user.username.substring(0, 2).toUpperCase();

            // Мок-данные для статистики (в реальном приложении их нужно загружать)
            createdStat.textContent = new Date().toLocaleDateString(); // Замените на 'user.created_at'

            // Здесь можно загрузить сохраненные данные (фамилию, телефон), если они есть
            // surnameField.value = user.surname || '';
            // phoneField.value = user.phone || '';


        } catch (error) {
            console.error("Не удалось загрузить профиль:", error);
            // Если любая другая ошибка - тоже выходим
            localStorage.removeItem("access_token");
            window.location.href = "/";
        }
    }

    // 4. ОБРАБОТКА СОХРАНЕНИЯ
    profileForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        // Здесь будет логика сохранения данных (отправка на бэкенд)
        const surname = surnameField.value;
        const phone = phoneField.value;

        console.log("Сохранение данных:", { surname, phone });

        // В реальном приложении:
        // await fetch("/api/profile/update", { ... });

        alert("Данные (пока что) сохранены в консоли!");
    });

    // Запускаем загрузку данных при открытии страницы
    fetchProfileData();
});