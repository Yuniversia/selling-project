python -m venv auth

source auth/bin/activate

pip install fastapi uvicorn sqlmodel bcrypt python-jose[cryptography] authlib httpx itsdangerous

```shell
uvicorn main:app --reload
```

or for Windows

```shell
python -m uvicorn main:app --reload
```