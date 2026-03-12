# Plan: Bot de WhatsApp para Agendamiento

## Opciones de API de WhatsApp

### Opción A — Meta WhatsApp Business Platform (oficial)
- **Costo**: Gratis hasta 1,000 conversaciones/mes; luego pago por conversación
- **Pros**: Directo con Meta, sin intermediarios, mayor control
- **Contras**: Proceso de aprobación más largo, requiere cuenta de Meta Business verificada
- **Docs**: https://developers.facebook.com/docs/whatsapp/cloud-api

### Opción B — Twilio WhatsApp API (recomendada para arrancar rápido)
- **Costo**: ~$0.005/mensaje + sandbox gratis para desarrollo
- **Pros**: Setup en minutos con sandbox, SDK en Python, documentación excelente
- **Contras**: Intermediario (costo adicional), mismo proceso de aprobación Meta para producción
- **Docs**: https://www.twilio.com/docs/whatsapp

### Opción C — whatsapp-web.js (no oficial)
- **Costo**: Gratis
- **Pros**: Sin aprobaciones, arranque inmediato
- **Contras**: Viola ToS de WhatsApp, riesgo de ban, requiere sesión activa de navegador, no apto para producción

**Recomendación**: Usar **Twilio** en desarrollo/staging y migrar a **Meta Cloud API** en producción.

---

## Arquitectura Propuesta

```
Usuario WhatsApp
      │
      ▼
[WhatsApp Business API]
      │ webhook POST
      ▼
[FastAPI — nuevo router /api/v1/whatsapp]
      │
      ├── Manejo de conversación (estado por número)
      │         └── Redis o DB (tabla conversation_state)
      │
      ├── Lógica del bot (flujo de agendamiento)
      │
      └── CRUD existente (appointments, work_schedules)
```

---

## Pasos de Implementación

### Paso 1 — Configurar cuenta y API

#### Con Twilio (desarrollo):
1. Crear cuenta en https://www.twilio.com
2. Ir a **Messaging → Try it out → Send a WhatsApp message**
3. Activar el sandbox de WhatsApp
4. Anotar: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`

#### Con Meta Cloud API (producción):
1. Crear app en https://developers.facebook.com → tipo "Business"
2. Agregar producto "WhatsApp"
3. Crear/vincular cuenta de **WhatsApp Business**
4. Verificar cuenta de negocio en Meta Business Manager
5. Obtener `WHATSAPP_TOKEN` y `PHONE_NUMBER_ID`
6. Configurar webhook con token de verificación propio

---

### Paso 2 — Instalar dependencias

```bash
pip install twilio redis
# o para Meta directamente:
pip install httpx redis
```

Agregar a `requirements.txt`:
```
twilio>=9.0.0
redis>=5.0.0
httpx>=0.28.0
```

---

### Paso 3 — Variables de entorno

Agregar a `.env`:
```
# Twilio (desarrollo)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Meta Cloud API (producción)
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=mi_token_secreto

# Redis (estado de conversación)
REDIS_URL=redis://localhost:6379
```

Agregar a `app/core/config.py`:
```python
twilio_account_sid: str = ""
twilio_auth_token: str = ""
twilio_whatsapp_number: str = ""
whatsapp_token: str = ""
whatsapp_phone_number_id: str = ""
whatsapp_verify_token: str = ""
redis_url: str = "redis://localhost:6379"
```

---

### Paso 4 — Diseño del flujo de conversación

```
[INICIO]
  └─→ "Hola" / cualquier mensaje
        └─→ Mostrar menú principal
              1. Agendar hora
              2. Ver mis citas
              3. Cancelar cita

[AGENDAR HORA]
  └─→ Listar comercios disponibles (providers)
        └─→ Usuario elige comercio
              └─→ Pedir fecha (ej: "15/03/2026")
                    └─→ Mostrar horarios disponibles
                          └─→ Usuario elige horario
                                └─→ Pedir nombre del servicio/motivo
                                      └─→ Confirmar → crear appointment
                                            └─→ "✅ Cita agendada para..."

[VER CITAS]
  └─→ Si el número no está registrado → pedir email
        └─→ Buscar citas activas
              └─→ Listar con estado y fecha

[CANCELAR CITA]
  └─→ Listar citas activas
        └─→ Usuario elige cuál cancelar
              └─→ Confirmación → cancelar appointment
```

---

### Paso 5 — Tabla de estado de conversación

Crear migración:
```bash
alembic revision --autogenerate -m "add whatsapp conversation state"
```

Modelo sugerido (`app/models/whatsapp_session.py`):
```python
class WhatsappSession(Base):
    __tablename__ = "whatsapp_sessions"

    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, index=True)
    state = Column(String, default="idle")        # estado del flujo
    context = Column(JSON, default={})            # datos parciales (provider elegido, fecha, etc.)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

Alternativamente, usar Redis con TTL de 30 minutos para mayor performance:
```python
# key: whatsapp:session:{phone_number}
# value: JSON con {state, context, user_id}
# TTL: 1800 segundos
```

---

### Paso 6 — Nuevo router en FastAPI

Crear `app/api/v1/endpoints/whatsapp.py`:

```python
from fastapi import APIRouter, Request, Response
from app.services.whatsapp_bot import WhatsAppBot

router = APIRouter()
bot = WhatsAppBot()

# Verificación del webhook (Meta)
@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == settings.whatsapp_verify_token:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(status_code=403)

# Recibir mensajes
@router.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    await bot.process_message(body, db)
    return {"status": "ok"}
```

Registrar en `app/main.py`:
```python
from app.api.v1.endpoints import whatsapp
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["whatsapp"])
```

---

### Paso 7 — Exponer el webhook (desarrollo local)

El webhook necesita ser accesible desde internet. Usar **ngrok**:

```bash
# Instalar ngrok: https://ngrok.com
ngrok http 8000
# Obtendrás una URL como: https://abc123.ngrok-free.app
# Configurar en Twilio/Meta: https://abc123.ngrok-free.app/api/v1/whatsapp/webhook
```

Para producción, el endpoint estará disponible directo en el dominio del servidor.

---

### Paso 8 — Vincular número de WhatsApp con usuario del sistema

Opciones:
- **Automático**: Al primer mensaje, pedir email → buscar en DB → vincular número con `users.phone_number`
- **Manual**: Admin vincula en panel

Agregar columna a `users`:
```bash
alembic revision --autogenerate -m "add phone_number to users"
```

---

### Paso 9 — Notificaciones proactivas (opcional pero valioso)

Una vez que el bot está activo, enviar mensajes automáticos:
- Recordatorio 24h antes de la cita
- Confirmación al crear/cancelar cita
- Notificación al proveedor cuando llega nueva cita

Esto requiere una tarea programada (APScheduler o Celery + Redis).

---

## Orden de trabajo sugerido

| Prioridad | Tarea |
|-----------|-------|
| 1 | Crear cuenta Twilio + activar sandbox |
| 2 | Agregar tabla `whatsapp_sessions` + migración |
| 3 | Crear servicio de envío de mensajes (wrapper Twilio/Meta) |
| 4 | Implementar router `/whatsapp/webhook` |
| 5 | Implementar flujo "Agendar hora" (el más importante) |
| 6 | Implementar flujos "Ver citas" y "Cancelar" |
| 7 | Pruebas con sandbox + ngrok |
| 8 | Solicitar número oficial Meta Business |
| 9 | Notificaciones proactivas (recordatorios) |

---

## Consideraciones importantes

- **Ventana de 24h**: WhatsApp solo permite enviar mensajes libres dentro de las 24h de la última interacción del usuario. Para notificaciones fuera de esa ventana se deben usar **Message Templates** aprobados por Meta.
- **Templates**: Registrar templates para: confirmación de cita, recordatorio, cancelación.
- **Idioma**: Los templates deben aprobarse en el idioma que se usará (español).
- **Rate limits**: Meta permite 80 mensajes/segundo por número de teléfono.
