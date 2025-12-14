# tests/helpers.py - Вспомогательные функции для тестов

import httpx
from typing import List, Optional, Any


class TestResult:
    """Класс для формирования читабельных сообщений об ошибках"""
    
    @staticmethod
    def format_error(
        test_name: str,
        expected: Any,
        actual: Any,
        response: Optional[httpx.Response] = None,
        details: str = ""
    ) -> str:
        """
        Форматирует сообщение об ошибке теста.
        
        Args:
            test_name: Название проверки (что проверяем)
            expected: Ожидаемое значение
            actual: Фактическое значение
            response: HTTP ответ (опционально)
            details: Дополнительные детали
        """
        lines = [
            "",
            "=" * 60,
            f"❌ ТЕСТ НЕ ПРОЙДЕН: {test_name}",
            "=" * 60,
            f"📋 Ожидалось: {expected}",
            f"📛 Получено:  {actual}",
        ]
        
        if response is not None:
            lines.extend([
                "",
                "📡 Детали HTTP ответа:",
                f"   URL: {response.url}",
                f"   Статус: {response.status_code} {response.reason_phrase}",
            ])
            
            # Пробуем добавить тело ответа (если JSON)
            try:
                body = response.json()
                lines.append(f"   Тело ответа: {body}")
            except:
                if len(response.text) < 500:
                    lines.append(f"   Тело ответа: {response.text[:500]}")
                else:
                    lines.append(f"   Тело ответа: {response.text[:500]}...")
        
        if details:
            lines.extend(["", f"ℹ️  Подробности: {details}"])
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    @staticmethod
    def status_check(
        response: httpx.Response,
        expected_codes: List[int],
        test_name: str
    ) -> None:
        """
        Проверяет статус код ответа с читабельным сообщением.
        
        Args:
            response: HTTP ответ
            expected_codes: Список допустимых кодов
            test_name: Название теста
        """
        if response.status_code not in expected_codes:
            raise AssertionError(
                TestResult.format_error(
                    test_name=test_name,
                    expected=f"Статус код из {expected_codes}",
                    actual=f"Статус код {response.status_code}",
                    response=response
                )
            )
    
    @staticmethod
    def json_field_check(
        data: dict,
        field: str,
        test_name: str,
        expected_value: Any = None
    ) -> None:
        """
        Проверяет наличие поля в JSON с читабельным сообщением.
        """
        if field not in data:
            raise AssertionError(
                TestResult.format_error(
                    test_name=test_name,
                    expected=f"Поле '{field}' в ответе",
                    actual=f"Поля '{field}' нет. Есть: {list(data.keys())}",
                    details=f"Полученные данные: {data}"
                )
            )
        
        if expected_value is not None and data[field] != expected_value:
            raise AssertionError(
                TestResult.format_error(
                    test_name=test_name,
                    expected=f"Поле '{field}' = {expected_value}",
                    actual=f"Поле '{field}' = {data[field]}",
                    details=f"Полученные данные: {data}"
                )
            )


def assert_status(response: httpx.Response, expected: List[int], test_name: str):
    """Удобная функция для проверки статуса"""
    TestResult.status_check(response, expected, test_name)


def assert_json_field(data: dict, field: str, test_name: str, value: Any = None):
    """Удобная функция для проверки JSON поля"""
    TestResult.json_field_check(data, field, test_name, value)
