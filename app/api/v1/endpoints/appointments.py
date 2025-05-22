from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas.appointment import Appointment, AppointmentCreate, AppointmentUpdate
from app.models.appointment import Appointment as AppointmentModel, AppointmentStatus
from app.models.user import User, UserRole
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, and_, or_

router = APIRouter()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@router.post("/", response_model=Appointment)
def create_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_in: AppointmentCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new appointment (only clients can create appointments)
    """
    try:
        logger.debug(f"Creating appointment with data: {appointment_in}")
        logger.debug(f"Current user: {current_user}")

        if current_user.role != UserRole.CLIENT:
            raise HTTPException(
                status_code=400, detail="Only clients can create appointments"
            )

        # Verificar que el proveedor existe
        provider = (
            db.query(User)
            .filter(
                User.id == appointment_in.provider_id, User.role == UserRole.PROVIDER
            )
            .first()
        )
        logger.debug(f"Provider found: {provider}")
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Verificar disponibilidad
        appointment_start = appointment_in.date_time
        appointment_end = appointment_start + timedelta(
            minutes=appointment_in.duration_minutes
        )

        overlapping = (
            db.query(AppointmentModel)
            .filter(
                AppointmentModel.provider_id == appointment_in.provider_id,
                or_(
                    and_(
                        AppointmentModel.date_time <= appointment_start,
                        AppointmentModel.date_time + timedelta(minutes=30)
                        > appointment_start,
                    ),
                    and_(
                        AppointmentModel.date_time < appointment_end,
                        AppointmentModel.date_time + timedelta(minutes=30)
                        >= appointment_end,
                    ),
                ),
            )
            .first()
        )
        logger.debug(f"Overlapping appointment found: {overlapping}")

        if overlapping:
            raise HTTPException(
                status_code=400, detail="Provider is not available at this time"
            )

        try:
            appointment = AppointmentModel(
                title=appointment_in.title,
                description=appointment_in.description,
                date_time=appointment_in.date_time,
                duration_minutes=appointment_in.duration_minutes,
                provider_id=appointment_in.provider_id,
                client_id=current_user.id,
                status=AppointmentStatus.PENDING,
            )
            logger.debug(f"Created appointment object: {appointment}")
            db.add(appointment)
            logger.debug("Added appointment to session")
            db.commit()
            logger.debug("Committed appointment to database")
            db.refresh(appointment)
            logger.debug(f"Refreshed appointment: {appointment}")
            return appointment
        except Exception as e:
            logger.error(f"Error in database operations: {str(e)}")
            db.rollback()
            raise
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating appointment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating appointment: {str(e)}",
        )


@router.get("/me", response_model=List[Appointment])
def read_own_appointments(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get own appointments (as client or provider)
    """
    if current_user.role == UserRole.CLIENT:
        appointments = (
            db.query(AppointmentModel)
            .filter(AppointmentModel.client_id == current_user.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    else:
        appointments = (
            db.query(AppointmentModel)
            .filter(AppointmentModel.provider_id == current_user.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    return appointments


@router.get("/{appointment_id}", response_model=Appointment)
def read_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get appointment by ID
    """
    appointment = (
        db.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if (
        appointment.client_id != current_user.id
        and appointment.provider_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return appointment


@router.put("/{appointment_id}", response_model=Appointment)
def update_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    appointment_in: AppointmentUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update appointment
    """
    appointment = (
        db.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Solo el cliente puede modificar la cita si está pendiente
    # El proveedor puede actualizar el estado
    if current_user.id == appointment.client_id:
        if appointment.status != "pending":
            raise HTTPException(
                status_code=400, detail="Can only modify pending appointments"
            )
    elif current_user.id == appointment.provider_id:
        # El proveedor solo puede actualizar el estado
        if appointment_in.model_dump(exclude_unset=True).keys() != {"status"}:
            raise HTTPException(
                status_code=400, detail="Providers can only update appointment status"
            )
    else:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    for field, value in appointment_in.model_dump(exclude_unset=True).items():
        setattr(appointment, field, value)

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """
    Delete appointment (only clients can delete pending appointments)
    """
    appointment = (
        db.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.id != appointment.client_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if appointment.status != "pending":
        raise HTTPException(
            status_code=400, detail="Can only delete pending appointments"
        )

    db.delete(appointment)
    db.commit()
