
python -m venv auth

source auth/bin/activate

## Start project

pip install fastapi uvicorn sqlmodel bcrypt python-jose[cryptography] authlib httpx itsdangerous python-multipart

uvicorn main:app --port 8000 --reload


or for Windows

```shell
python -m uvicorn main:app --reload
```