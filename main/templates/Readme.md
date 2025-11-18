python -m venv front

source front/bin/activate

uvicorn main:app --port 5500 --reload