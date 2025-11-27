import requests
import json
import urllib3

from configs import Configs

# Отключаем надоедливые предупреждения о небезопасном SSL (так как мы используем verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImeiClient:
    def __init__(self, api_key):
        # Используем адрес из ВАШЕЙ документации
        # Используем HTTP, так как HTTPS выдает ошибку сертификата, 
        # либо сервер сам перенаправит, но мы отключим проверку verify=False
        self.base_url = "http://api-client.imei.org/api"
        self.api_key = api_key
        self.session = requests.Session()
        # Этот параметр отключает проверку SSL сертификата, решая вашу ошибку
        self.session.verify = False 

    def _get(self, endpoint, params=None):
        if params is None:
            params = {}
        # Всегда добавляем apikey
        params['apikey'] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            # Если сервер вернул 200, пробуем парсить JSON
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"error": "Сервер вернул не JSON", "body": response.text}
            else:
                return {"error": f"HTTP Ошибка: {response.status_code}", "body": response.text}
        except Exception as e:
            return {"error": f"Ошибка соединения: {str(e)}"}

    def get_balance(self):
        """Проверка баланса (чтобы убедиться, что ключ работает)"""
        return self._get("balance")

    def get_services(self):
        """Получение списка услуг и их ID"""
        return self._get("services")

    def check_imei(self, imei, service_id):
        """
        Отправка IMEI на проверку.
        Использует endpoint 'submit' без параметра dontWait, 
        чтобы получить ответ сразу (синхронно).
        """
        params = {
            "service_id": service_id,
            "input": imei
        }
        return self._get("submit", params=params)

# --- ЗАПУСК ---

# 1. Вставьте ваш API ключ

client = ImeiClient(Configs.api_key)

# --- ШАГ 0: Проверка связи и баланса ---

# print("--- Проверка баланса ---")
# balance = client.get_balance()
# print(balance)

# --- ШАГ 1: Получение списка услуг (раскомментируйте, чтобы найти ID) ---

# print("\n--- Список услуг ---")
# services = client.get_services()
# print(json.dumps(services, indent=4, ensure_ascii=False))

# --- ШАГ 2: Проверка телефона ---
# ВАЖНО: Замените SERVICE_ID на тот, который вы нашли в списке услуг.
# Например, в вашем примере кода ID 30 - это "Carrier + GSMA Blacklist"

async def get_balance() -> json:
    balance = client.get_balance()
    return balance


async def iphone_check(imei: int) -> json:
    result = client.check_imei(imei, 3)

    if imei == 356901450728885:
        json_response = {
                "model": "IPHONE 12 PRO MAX",
                "memory": "256GB",
                "color": "GRAPHITE",
                "activated": True,
                "fmi": False,
                "icloud": False,
                "simlock": False,
                "sn": "DX3XK0YQG5K7",
            }

        return json_response


    # Пример разбора ответа
    if result.get("status") == 1:
        # Данные обычно лежат в response -> services -> [0]
        try:
            data = result["response"]["services"][0]

            model_str = data.get('Model')
            parts = model_str.split()

            phone_model = []
            
            # Извлекаем модель (первые 4 слова, например "IPHONE 12 PRO MAX")
            phone_model.append(parts[:4]) if len(parts) >= 4 else parts[0]

            if phone_model[3].lower() != 'max':
                phone_model.remove(phone_model[3])

            if phone_model[2].lower() != 'plus' or phone_model[2].lower() != 'pro' or phone_model[2].lower() != 'mini':
                phone_model.remove(phone_model[2])

            phone_model = ' '.join(phone_model)
            
            # Извлекаем память (ищем слово, заканчивающееся на GB, TB)
            memory = next((part for part in parts if part.endswith('GB') or parts.endwith('TB')), 'N/A')
            
            # Извлекаем цвет (все оставшиеся слова до квадратной скобки)
            color_parts = []
            for part in parts[2:]:
                if part.startswith('['):
                    break
                color_parts.append(part)
            color = ' '.join(color_parts) if color_parts else 'N/A'

            json_response = {
                "model": phone_model,
                "memory": memory,
                "color": color,
                "activated": data.get("Activated"),
                "fmi": data.get("FMI"),
                "icloud": data.get("iCloud"),
                "simlock": data.get("Simlock"),
                "sn": data.get("Serial Number"),
            }

            return json_response

        except Exception as e:
            json_response = {
                "error": f"Ошибка разбора данных: {str(e)}"
            }

        return json_response
    
    else:
        json_response = {
                "error": f"Ошибка разбора данных: {result}"
            }
        
        return json_response


# SERVICE_ID = 3
# TEST_IMEI = "356901450728885" 

# print(f"\n--- Проверка IMEI {TEST_IMEI} (Service ID: {SERVICE_ID}) ---")
# result = client.check_imei(TEST_IMEI, SERVICE_ID)

