"""Утилиты для работы с IMEI"""


def validate_imei(imei: str) -> bool:
    """
    Проверка IMEI по алгоритму Luhn
    
    Args:
        imei: строка из 15 цифр
    
    Returns:
        True если контрольная сумма верна
    """
    if len(imei) != 15 or not imei.isdigit():
        return False
    
    def luhn_checksum(number: str) -> int:
        """Вычисление контрольной суммы Luhn"""
        digits = [int(d) for d in str(number)]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum([int(x) for x in str(d * 2)])
        return checksum % 10
    
    return luhn_checksum(imei) == 0


def parse_memory(memory_str: str) -> int:
    """
    Парсит строку памяти в число
    
    Examples:
        "128GB" -> 128
        "256" -> 256
        "1TB" -> 1024
    """
    if not memory_str:
        return None
    
    memory_str = str(memory_str).upper().strip()
    
    # Убираем GB
    memory_str = memory_str.replace("GB", "").replace("G", "").strip()
    
    # Конвертируем TB
    if "TB" in memory_str or "T" in memory_str:
        memory_str = memory_str.replace("TB", "").replace("T", "").strip()
        try:
            return int(float(memory_str) * 1024)
        except ValueError:
            return None
    
    try:
        return int(memory_str)
    except ValueError:
        return None
