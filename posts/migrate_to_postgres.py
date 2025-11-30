# migrate_to_postgres.py
# Скрипт для создания всех таблиц в PostgreSQL

from sqlmodel import SQLModel, create_engine
import os
import sys

# Добавляем пути к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'auth'))
sys.path.append(os.path.dirname(__file__))

# Загружаем переменные окружения из .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    print("✅ Загружены переменные из .env")
except ImportError:
    print("⚠️ python-dotenv не установлен, используются значения по умолчанию")

# PostgreSQL Configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "lais_marketplace")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"Подключаемся к PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")

try:
    # Создаем движок
    engine = create_engine(DATABASE_URL, echo=True)
    
    # Импортируем все модели
    print("\nИмпортируем модели...")
    
    # Auth models - импортируем User
    auth_models_path = os.path.join(os.path.dirname(__file__), '..', 'auth', 'models.py')
    auth_spec = __import__('importlib.util').util.spec_from_file_location("auth_models", auth_models_path)
    auth_models_module = __import__('importlib.util').util.module_from_spec(auth_spec)
    auth_spec.loader.exec_module(auth_models_module)
    User = auth_models_module.User
    print("✅ User модель импортирована")
    
    # Posts models - импортируем Iphone
    posts_models_path = os.path.join(os.path.dirname(__file__), 'models.py')
    posts_spec = __import__('importlib.util').util.spec_from_file_location("posts_models", posts_models_path)
    posts_models_module = __import__('importlib.util').util.module_from_spec(posts_spec)
    posts_spec.loader.exec_module(posts_models_module)
    Iphone = posts_models_module.Iphone
    print("✅ Iphone модель импортирована")
    
    # Bought models
    from bought_models import BoughtItem
    print("✅ BoughtItem модель импортирована")
    
    # Создаем все таблицы
    print("\nСоздаём таблицы в PostgreSQL...")
    SQLModel.metadata.create_all(engine)
    
    print("\n✅ Все таблицы успешно созданы!")
    print("\nСозданные таблицы:")
    print("  - user (auth)")
    print("  - iphone (posts)")
    print("  - bought (posts)")
    
    # Тестовое подключение
    from sqlmodel import Session, select
    with Session(engine) as session:
        result = session.execute(select(1))
        print("\n✅ Тестовое подключение успешно!")
    
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    print("\nПроверьте:")
    print("1. PostgreSQL запущен")
    print("2. База данных 'lais_marketplace' существует")
    print("3. Учетные данные правильные")
    print("4. Установлен psycopg2: pip install psycopg2-binary")
    sys.exit(1)
