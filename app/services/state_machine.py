"""
Máquina de estados para el flujo de agendamiento por WhatsApp.

Flujo: INICIO → ELIGIENDO_SERVICIO → ELIGIENDO_DIA → ELIGIENDO_HORA → CONFIRMANDO → CONFIRMADO
"""

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.models.user import User, UserRole
from app.crud.crud_work_schedule import work_schedule_crud
from app.crud.crud_appointment import appointment as appointment_crud
from app.schemas.appointment import AppointmentCreate

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SERVICIOS = [
    {"id": 1, "nombre": "Consulta General", "duracion": 30},
    {"id": 2, "nombre": "Consulta de Seguimiento", "duracion": 30},
    {"id": 3, "nombre": "Revisión", "duracion": 30},
]

AFIRMACIONES = {"si", "sí", "yes", "s", "1", "ok", "confirmar", "confirmo"}
NEGACIONES = {"no", "n", "0", "cancelar", "cancel"}


def process_message(
    state: str,
    context: dict,
    message: str,
    db: Session,
    phone: str = "",
) -> tuple[str, str, dict]:
    """
    Procesa un mensaje entrante y retorna (respuesta, nuevo_estado, nuevo_contexto).

    Args:
        state: Estado actual de la conversación.
        context: Datos intermedios acumulados (servicio, día, hora, etc.).
        message: Texto del mensaje recibido.
        db: Sesión de base de datos.
        phone: Número de teléfono del remitente.
    """
    msg = message.strip().lower()

    # Siempre mantener el teléfono en el contexto
    ctx = {**context, "phone": phone} if phone else context

    # Reiniciar si ya terminó el flujo anterior
    if state == "CONFIRMADO":
        state = "INICIO"

    handlers = {
        "INICIO": _handle_inicio,
        "ELIGIENDO_SERVICIO": _handle_eligiendo_servicio,
        "ELIGIENDO_DIA": _handle_eligiendo_dia,
        "ELIGIENDO_HORA": _handle_eligiendo_hora,
        "CONFIRMANDO": _handle_confirmando,
    }

    handler = handlers.get(state, _handle_inicio)
    return handler(ctx, msg, db)


# ---------------------------------------------------------------------------
# Handlers por estado
# ---------------------------------------------------------------------------

def _handle_inicio(context: dict, msg: str, db: Session) -> tuple[str, str, dict]:
    provider = db.query(User).filter(User.role == UserRole.PROVIDER).first()
    if not provider:
        return (
            "Lo sentimos, el sistema de agendamiento no está disponible en este momento.",
            "INICIO",
            context,
        )

    new_context = {"provider_id": provider.id, "phone": context.get("phone", "")}
    servicios_texto = "\n".join(f"{s['id']}. {s['nombre']}" for s in SERVICIOS)

    response = (
        "¡Hola! Bienvenido al sistema de agendamiento.\n\n"
        "¿Qué tipo de cita necesitas?\n"
        f"{servicios_texto}\n\n"
        "Responde con el número o el nombre del servicio."
    )
    return response, "ELIGIENDO_SERVICIO", new_context


def _handle_eligiendo_servicio(context: dict, msg: str, db: Session) -> tuple[str, str, dict]:
    servicio = None

    if msg.strip() in ("1", "2", "3"):
        servicio = SERVICIOS[int(msg.strip()) - 1]
    else:
        for s in SERVICIOS:
            if msg in s["nombre"].lower() or s["nombre"].lower() in msg:
                servicio = s
                break

    if not servicio:
        servicios_texto = "\n".join(f"{s['id']}. {s['nombre']}" for s in SERVICIOS)
        return (
            f"No reconocí tu respuesta. Por favor elige:\n{servicios_texto}",
            "ELIGIENDO_SERVICIO",
            context,
        )

    new_context = {**context, "servicio": servicio["nombre"], "duracion": servicio["duracion"]}
    return (
        f"Perfecto, {servicio['nombre']}. \n\n"
        "¿Para qué fecha? Puedes escribir:\n"
        "- hoy / mañana\n"
        "- DD/MM/YYYY (ej: 15/04/2026)\n"
        "- YYYY-MM-DD (ej: 2026-04-15)",
        "ELIGIENDO_DIA",
        new_context,
    )


def _parse_date(msg: str) -> Optional[date]:
    msg = msg.strip().lower()

    if msg in ("hoy", "today"):
        return date.today()
    if msg in ("mañana", "manana", "tomorrow"):
        return date.today() + timedelta(days=1)

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m", "%d-%m"):
        try:
            parsed = datetime.strptime(msg, fmt)
            if "%Y" not in fmt:
                parsed = parsed.replace(year=date.today().year)
            return parsed.date()
        except ValueError:
            continue

    return None


def _handle_eligiendo_dia(context: dict, msg: str, db: Session) -> tuple[str, str, dict]:
    target_date = _parse_date(msg)

    if not target_date:
        return (
            "No pude interpretar la fecha. Intenta con DD/MM/YYYY (ej: 15/04/2026) "
            "o escribe hoy o mañana.",
            "ELIGIENDO_DIA",
            context,
        )

    if target_date < date.today():
        return (
            "No se puede agendar en fechas pasadas. ¿Qué otra fecha te viene bien?",
            "ELIGIENDO_DIA",
            context,
        )

    provider_id = context.get("provider_id")
    availability = work_schedule_crud.get_provider_availability_for_date(
        db, provider_id, target_date
    )

    if not availability["is_available"] or not availability["available_slots"]:
        return (
            f"Lo siento, el {target_date.strftime('%d/%m/%Y')} no hay disponibilidad "
            f"({availability['reason']}). ¿Tienes otra fecha en mente?",
            "ELIGIENDO_DIA",
            context,
        )

    slots = availability["available_slots"]
    slots_texto = "\n".join(
        f"{i + 1}. {s['start']} - {s['end']}" for i, s in enumerate(slots)
    )
    new_context = {
        **context,
        "dia": target_date.isoformat(),
        "slots_disponibles": [s["start"] for s in slots],
    }

    return (
        f"Horarios disponibles para el {target_date.strftime('%d/%m/%Y')}:\n\n"
        f"{slots_texto}\n\n"
        "Responde con el número o la hora (ej: 09:30).",
        "ELIGIENDO_HORA",
        new_context,
    )


def _handle_eligiendo_hora(context: dict, msg: str, db: Session) -> tuple[str, str, dict]:
    slots = context.get("slots_disponibles", [])
    hora_elegida = None

    msg_clean = msg.strip()

    # Selección por número
    if re.match(r"^\d+$", msg_clean) and 1 <= int(msg_clean) <= len(slots):
        hora_elegida = slots[int(msg_clean) - 1]
    else:
        # Normalizar hora con un solo dígito: "9:00" → "09:00"
        if re.match(r"^\d:\d{2}$", msg_clean):
            msg_clean = "0" + msg_clean
        if msg_clean in slots:
            hora_elegida = msg_clean

    if not hora_elegida:
        slots_texto = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(slots))
        return (
            f"No reconocí tu selección. Elige un horario:\n{slots_texto}",
            "ELIGIENDO_HORA",
            context,
        )

    new_context = {**context, "hora": hora_elegida}
    dia = context.get("dia", "")
    servicio = context.get("servicio", "")

    try:
        fecha_fmt = datetime.fromisoformat(dia).strftime("%d/%m/%Y")
    except ValueError:
        fecha_fmt = dia

    return (
        "Resumen de tu cita:\n"
        f"- Servicio: {servicio}\n"
        f"- Fecha: {fecha_fmt}\n"
        f"- Hora: {hora_elegida}\n\n"
        "¿Confirmas? Responde SI para confirmar o NO para cancelar.",
        "CONFIRMANDO",
        new_context,
    )


def _handle_confirmando(context: dict, msg: str, db: Session) -> tuple[str, str, dict]:
    msg_clean = msg.strip().lower()

    if msg_clean in NEGACIONES:
        return (
            "Cita cancelada. Escribe cualquier mensaje para empezar de nuevo.",
            "CONFIRMADO",
            {},
        )

    if msg_clean not in AFIRMACIONES:
        return (
            "No entendí tu respuesta. Escribe SI para confirmar o NO para cancelar.",
            "CONFIRMANDO",
            context,
        )

    # Crear la cita
    provider_id = context.get("provider_id")
    servicio = context.get("servicio", "Consulta")
    dia = context.get("dia")
    hora = context.get("hora")
    duracion = context.get("duracion", 30)
    phone = context.get("phone", "unknown")

    client = _get_or_create_whatsapp_client(db, phone)

    try:
        date_time = datetime.fromisoformat(f"{dia}T{hora}:00").replace(tzinfo=timezone.utc)
        appt_in = AppointmentCreate(
            title=servicio,
            description="Cita agendada por WhatsApp",
            date_time=date_time,
            duration_minutes=duracion,
            provider_id=provider_id,
        )
        appointment_crud.create(db=db, obj_in=appt_in, client_id=client.id)
    except Exception as e:
        return (
            f"Hubo un error al crear tu cita: {e}\n"
            "Escribe cualquier mensaje para intentarlo de nuevo.",
            "CONFIRMADO",
            {},
        )

    try:
        fecha_fmt = datetime.fromisoformat(dia).strftime("%d/%m/%Y")
    except ValueError:
        fecha_fmt = dia

    return (
        "¡Cita confirmada!\n\n"
        f"Servicio: {servicio}\n"
        f"Fecha: {fecha_fmt}\n"
        f"Hora: {hora}\n\n"
        "Te esperamos. Para cancelar o reagendar, contáctanos.",
        "CONFIRMADO",
        {},
    )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _get_or_create_whatsapp_client(db: Session, phone: str) -> User:
    """Encuentra o crea un usuario CLIENT para el número de WhatsApp dado."""
    clean_phone = re.sub(r"\D", "", phone)
    email = f"{clean_phone}@whatsapp.guest"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=_pwd_context.hash(secrets.token_hex(16)),
            role=UserRole.CLIENT,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
