# Sistema de Citas (Appointment System)

Sistema de gestión de citas con autenticación JWT y roles de usuario.

## Características

- Autenticación JWT
- Roles de usuario (cliente y proveedor)
- Base de datos PostgreSQL
- Migraciones con Alembic
- API RESTful con FastAPI
- Documentación automática con Swagger UI

## Requisitos

- Python 3.10+
- PostgreSQL 14+
- pip (gestor de paquetes de Python)

## Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd appointment-system
```

2. Crear un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
Crear un archivo `.env` con:
```env
SECRET_KEY="tu_clave_secreta_aqui"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL="postgresql://user:password@localhost:5432/appointment_db"
```

5. Configurar la base de datos:
```bash
# Crear usuario y base de datos en PostgreSQL
psql postgres -c "CREATE USER \"user\" WITH PASSWORD 'password' CREATEDB;"
psql postgres -c "CREATE DATABASE appointment_db OWNER \"user\";"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE appointment_db TO \"user\";"

# Ejecutar migraciones
alembic upgrade head
```

## Uso

1. Iniciar el servidor:
```bash
uvicorn app.main:app --reload
```

2. Acceder a la documentación:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints principales

### Autenticación

- `POST /api/v1/register`: Registro de usuario
  ```json
  {
    "email": "usuario@ejemplo.com",
    "password": "contraseña123",
    "role": "client"
  }
  ```

- `POST /api/v1/login`: Inicio de sesión
  ```json
  {
    "username": "usuario@ejemplo.com",
    "password": "contraseña123"
  }
  ```

- `GET /api/v1/me`: Obtener perfil del usuario actual
  ```bash
  # Requiere header de autorización:
  Authorization: Bearer <token>
  ```

## Desarrollo

### Estructura del proyecto
```
app/
├── api/
│   ├── v1/
│   │   └── endpoints/
│   │       └── auth.py
│   └── deps.py
├── core/
│   ├── config.py
│   └── security.py
├── db/
│   └── session.py
├── models/
│   └── user.py
├── schemas/
│   └── user.py
└── main.py
```

### Migraciones

Para crear una nueva migración:
```bash
alembic revision --autogenerate -m "descripción del cambio"
```

Para aplicar migraciones:
```bash
alembic upgrade head
```

## Licencia

MIT 