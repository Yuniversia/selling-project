"""Configuration for main service (Frontend renderer)"""
import os


class Configs:
    """Конфигурация доставки для frontend"""
    
    # Стоимость доставки в евро (€)
    # Загружаются из переменных окружения или используются значения по умолчанию
    DELIVERY_COST_PICKUP = float(os.getenv('DELIVERY_COST_PICKUP', '0'))
    DELIVERY_COST_DPD = float(os.getenv('DELIVERY_COST_DPD', '2.99'))
    DELIVERY_COST_OMNIVA = float(os.getenv('DELIVERY_COST_OMNIVA', '1.99'))
    
    @classmethod
    def to_dict(cls):
        """Преобразовать конфиги в словарь для API"""
        return {
            'pickup': cls.DELIVERY_COST_PICKUP,
            'dpd': cls.DELIVERY_COST_DPD,
            'omniva': cls.DELIVERY_COST_OMNIVA
        }
