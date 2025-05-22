# Sistema de Citas (Appointment System)

Sistema de gestión de citas con autenticación JWT, roles de usuario y validación de disponibilidad.

## Características

- Autenticación JWT con manejo seguro de tokens
- Roles de usuario (cliente y proveedor)
- Base de datos PostgreSQL con relaciones y restricciones
- Migraciones automáticas con Alembic
- API RESTful con FastAPI
- Documentación automática con Swagger UI
- Validación de superposición de citas
- Manejo de zonas horarias
- Sistema de estados de citas (pending, confirmed, cancelled, completed)
- Control de acceso basado en roles

## Requisitos

- Python 3.10+
- PostgreSQL 14+
- pip (gestor de paquetes de Python)

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/m0ramax/appointment-system.git
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

## Endpoints

### Autenticación

- `POST /api/v1/register`: Registro de usuario
  ```json
  {
    "email": "usuario@ejemplo.com",
    "password": "contraseña123",
    "role": "client"  // "client" o "provider"
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

### Gestión de Citas

- `POST /api/v1/appointments/`: Crear nueva cita
  ```json
  {
    "title": "Consulta General",
    "description": "Primera consulta",
    "date_time": "2025-05-23T14:00:00Z",
    "duration_minutes": 30,
    "provider_id": 4
  }
  ```

- `GET /api/v1/appointments/me`: Listar citas del usuario actual

- `GET /api/v1/appointments/{appointment_id}`: Obtener detalles de una cita

- `PUT /api/v1/appointments/{appointment_id}`: Actualizar cita
  ```json
  {
    "status": "confirmed"  // Solo proveedores pueden confirmar
  }
  ```

- `DELETE /api/v1/appointments/{appointment_id}`: Cancelar cita

## Reglas de Negocio

### Estados de Citas
- **pending**: Estado inicial al crear una cita
- **confirmed**: Cuando el proveedor acepta la cita
- **cancelled**: Cuando se cancela la cita
- **completed**: Cuando la cita ha finalizado

### Permisos por Rol
- **Clientes**:
  - Pueden crear citas
  - Pueden ver sus propias citas
  - Pueden cancelar citas pendientes
  - No pueden modificar citas confirmadas

- **Proveedores**:
  - Pueden ver todas sus citas asignadas
  - Pueden confirmar/rechazar citas
  - Pueden marcar citas como completadas
  - Tienen acceso a su calendario de disponibilidad

### Validaciones
- No se permiten citas superpuestas para un mismo proveedor
- Las citas deben programarse con anticipación
- La duración mínima de una cita es de 30 minutos
- Se valida la disponibilidad del proveedor antes de confirmar

## Estructura del Proyecto
```
app/
├── api/
│   ├── v1/
│   │   └── endpoints/
│   │       ├── appointments.py
│   │       └── auth.py
│   └── deps.py
├── core/
│   ├── config.py
│   └── security.py
├── db/
│   └── session.py
├── models/
│   ├── appointment.py
│   └── user.py
├── schemas/
│   ├── appointment.py
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

## Contribuir

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

MIT 