from sqlalchemy.orm import Session
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from datetime import timedelta, datetime, timezone
from sqlalchemy import and_, or_, func, text
from fastapi import HTTPException, status
from typing import List, Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class CRUDAppointment:
    # Define valid state transitions
    VALID_TRANSITIONS: Dict[AppointmentStatus, List[AppointmentStatus]] = {
        AppointmentStatus.PENDING: [AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED],
        AppointmentStatus.CONFIRMED: [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED],
        AppointmentStatus.CANCELLED: [],  # Terminal state
        AppointmentStatus.COMPLETED: []   # Terminal state
    }
    
    # Define who can perform each transition
    TRANSITION_PERMISSIONS: Dict[tuple, UserRole] = {
        (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED): UserRole.PROVIDER,
        (AppointmentStatus.PENDING, AppointmentStatus.CANCELLED): None,  # Both can cancel pending
        (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED): UserRole.PROVIDER,
        (AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED): None,  # Both can cancel confirmed
    }

    def _validate_status_transition(
        self, 
        current_status: AppointmentStatus, 
        new_status: AppointmentStatus,
        user_role: UserRole,
        appointment: Appointment
    ) -> None:
        """
        Validate if a status transition is allowed based on business rules
        """
        # Check if transition is valid
        if new_status not in self.VALID_TRANSITIONS.get(current_status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {current_status.value} to {new_status.value}"
            )
        
        # Check permissions for this transition
        required_role = self.TRANSITION_PERMISSIONS.get((current_status, new_status))
        
        if required_role is not None and user_role != required_role:
            action_name = {
                AppointmentStatus.CONFIRMED: "confirm",
                AppointmentStatus.COMPLETED: "complete"
            }.get(new_status, "update")
            
            raise HTTPException(
                status_code=403,
                detail=f"Only {required_role.value}s can {action_name} appointments"
            )
        
        # Additional business rules
        if new_status == AppointmentStatus.COMPLETED:
            # Can only complete appointments that are today or in the past
            appointment_date = appointment.date_time.date()
            today = datetime.now(timezone.utc).date()
            
            if appointment_date > today:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot complete appointments scheduled for future dates"
                )
        
        if new_status == AppointmentStatus.CONFIRMED:
            # Cannot confirm appointments in the past or same day (within 1 hour)
            appointment_datetime = appointment.date_time
            now = datetime.now(timezone.utc)
            
            if appointment_datetime <= now + timedelta(hours=1):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot confirm appointments that are in the past or starting within 1 hour"
                )
    def get(self, db: Session, id: Any) -> Optional[Appointment]:
        return db.query(Appointment).filter(Appointment.id == id).first()

    def get_multi_by_user(
        self, db: Session, *, user: User, skip: int = 0, limit: int = 100
    ) -> List[Appointment]:
        if user.role == UserRole.CLIENT:
            return (
                db.query(Appointment)
                .filter(Appointment.client_id == user.id)
                .offset(skip)
                .limit(limit)
                .all()
            )
        else:
            return (
                db.query(Appointment)
                .filter(Appointment.provider_id == user.id)
                .offset(skip)
                .limit(limit)
                .all()
            )

    def _check_appointment_overlap(
        self, db: Session, provider_id: int, date_time: Any, duration_minutes: int, 
        exclude_appointment_id: Optional[int] = None
    ) -> None:
        """
        Check if the appointment would overlap with existing appointments
        Raises HTTPException if overlap is found
        """
        appointment_start = date_time
        appointment_end = appointment_start + timedelta(minutes=duration_minutes)
        
        # Query for potentially overlapping appointments
        query = db.query(Appointment).filter(
            Appointment.provider_id == provider_id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            # Check appointments in the same day for performance
            func.date(Appointment.date_time) == func.date(appointment_start)
        )
        
        # Exclude current appointment if updating
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)
            
        existing_appointments = query.all()
        
        # Check for time overlap
        for existing in existing_appointments:
            existing_start = existing.date_time
            existing_end = existing_start + timedelta(minutes=existing.duration_minutes)
            
            # Two appointments overlap if:
            # appointment_start < existing_end AND appointment_end > existing_start
            if appointment_start < existing_end and appointment_end > existing_start:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Time slot conflicts with existing appointment '{existing.title}' "
                           f"from {existing_start.strftime('%H:%M')} to {existing_end.strftime('%H:%M')}"
                )

    def create(
        self, db: Session, *, obj_in: AppointmentCreate, client_id: int
    ) -> Appointment:
        # Verificar que el proveedor existe
        provider = (
            db.query(User)
            .filter(User.id == obj_in.provider_id, User.role == UserRole.PROVIDER)
            .first()
        )
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Verificar que la cita no es en el pasado
        from datetime import datetime, timezone
        if obj_in.date_time < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400, 
                detail="Cannot create appointments in the past"
            )

        # Verificar que la duración es válida
        if obj_in.duration_minutes <= 0 or obj_in.duration_minutes > 480:  # Max 8 hours
            raise HTTPException(
                status_code=400, 
                detail="Duration must be between 1 and 480 minutes"
            )

        # Verificar superposición de horarios
        self._check_appointment_overlap(
            db=db, 
            provider_id=obj_in.provider_id, 
            date_time=obj_in.date_time, 
            duration_minutes=obj_in.duration_minutes
        )

        db_obj = Appointment(
            title=obj_in.title,
            description=obj_in.description,
            date_time=obj_in.date_time,
            duration_minutes=obj_in.duration_minutes,
            provider_id=obj_in.provider_id,
            client_id=client_id,
            status=AppointmentStatus.PENDING,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: Appointment, obj_in: AppointmentUpdate, user_role: UserRole
    ) -> Appointment:
        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Validate status transition if status is being updated
        if 'status' in update_data:
            new_status = update_data['status']
            self._validate_status_transition(
                current_status=db_obj.status,
                new_status=new_status,
                user_role=user_role,
                appointment=db_obj
            )
        
        # If updating date_time or duration, check for overlap
        if 'date_time' in update_data or 'duration_minutes' in update_data:
            new_date_time = update_data.get('date_time', db_obj.date_time)
            new_duration = update_data.get('duration_minutes', db_obj.duration_minutes)
            
            # Verificar que la nueva fecha no es en el pasado
            if new_date_time < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot reschedule appointments to the past"
                )
            
            # Verificar que la duración es válida
            if new_duration <= 0 or new_duration > 480:  # Max 8 hours
                raise HTTPException(
                    status_code=400, 
                    detail="Duration must be between 1 and 480 minutes"
                )
            
            # Cannot reschedule non-pending appointments
            if db_obj.status != AppointmentStatus.PENDING:
                raise HTTPException(
                    status_code=400,
                    detail="Can only reschedule pending appointments"
                )
            
            # Check for overlap with other appointments
            self._check_appointment_overlap(
                db=db,
                provider_id=db_obj.provider_id,
                date_time=new_date_time,
                duration_minutes=new_duration,
                exclude_appointment_id=db_obj.id
            )
        
        for field in update_data:
            setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> Appointment:
        obj = db.query(Appointment).get(id)
        db.delete(obj)
        db.commit()
        return obj


appointment = CRUDAppointment()
