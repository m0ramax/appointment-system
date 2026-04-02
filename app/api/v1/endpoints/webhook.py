"""
Webhook de WhatsApp para el flujo de agendamiento conversacional.

Soporta dos formatos de entrada:
- Twilio: multipart/form-data con campos From y Body
- Meta WhatsApp Cloud API: JSON con estructura entry[].changes[].value.messages[]

Verificación de webhook Meta: GET /webhook/whatsapp con hub.mode, hub.verify_token y hub.challenge.
"""

import os
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.conversation_state import ConversationState
from app.services.state_machine import process_message

router = APIRouter()

# En producción configura esto en settings / variable de entorno
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "agendya_verify_token")


@router.get("/webhook/whatsapp")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Endpoint de verificación para Meta WhatsApp Cloud API."""
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    return Response(status_code=403)


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Recibe mensajes entrantes de WhatsApp, los procesa con la máquina de estados
    y retorna la respuesta correspondiente.
    """
    content_type = request.headers.get("content-type", "")
    from_phone = ""
    message_body = ""
    is_twilio = False

    if "application/x-www-form-urlencoded" in content_type:
        # --- Twilio ---
        form = await request.form()
        raw_from = str(form.get("From", ""))
        from_phone = raw_from.replace("whatsapp:", "").strip()
        message_body = str(form.get("Body", "")).strip()
        is_twilio = True
    else:
        # --- Meta WhatsApp Cloud API ---
        try:
            body = await request.json()
        except Exception:
            return Response(status_code=400)

        # Ignorar notificaciones que no son mensajes (status updates, etc.)
        if body.get("object") != "whatsapp_business_account":
            return {"status": "ok"}

        try:
            msg_obj = body["entry"][0]["changes"][0]["value"]["messages"][0]
            if msg_obj.get("type") != "text":
                return {"status": "ok"}
            from_phone = msg_obj["from"]
            message_body = msg_obj["text"]["body"].strip()
        except (KeyError, IndexError):
            return {"status": "ok"}

    if not from_phone or not message_body:
        return {"status": "ok"}

    # Cargar o inicializar el estado de conversación
    conv = db.query(ConversationState).filter(ConversationState.phone == from_phone).first()
    if conv is None:
        conv = ConversationState(phone=from_phone, state="INICIO", context={})
        db.add(conv)
        db.flush()

    # Procesar mensaje en la máquina de estados
    response_text, new_state, new_context = process_message(
        state=conv.state,
        context=conv.context or {},
        message=message_body,
        db=db,
        phone=from_phone,
    )

    # Persistir nuevo estado
    conv.state = new_state
    conv.context = new_context
    db.commit()

    if is_twilio:
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{response_text}</Message></Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    return {"status": "ok", "reply": response_text}
