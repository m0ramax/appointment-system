from typing import List, Any
from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas.appointment import Appointment, AppointmentCreate, AppointmentUpdate, TimeSlot
from app.models.user import User, UserRole
from app.models.appointment import Appointment as AppointmentModel
from app.crud import crud_appointment

router = APIRouter()


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
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=400, detail="Only clients can create appointments"
        )
    appointment = crud_appointment.appointment.create(
        db=db, obj_in=appointment_in, client_id=current_user.id
    )
    return appointment


@router.get("/providers", response_model=List[dict])
def get_providers(
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Get list of all providers
    """
    providers = db.query(User).filter(User.role == UserRole.PROVIDER).all()
    
    return [
        {
            "id": provider.id,
            "email": provider.email,
            "name": provider.email.split("@")[0].title()  # Simple name from email
        }
        for provider in providers
    ]


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
    appointments = crud_appointment.appointment.get_multi_by_user(
        db=db, user=current_user, skip=skip, limit=limit
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
    appointment = crud_appointment.appointment.get(db=db, id=appointment_id)
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
    appointment = crud_appointment.appointment.get(db=db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Enhanced business logic for permissions based on user role
    update_data = appointment_in.model_dump(exclude_unset=True)
    
    if current_user.id == appointment.client_id:
        # Clients can only modify their own pending appointments
        # They can update title, description, date_time, duration, or cancel
        if appointment.status != AppointmentStatus.PENDING:
            raise HTTPException(
                status_code=400, 
                detail="Clients can only modify pending appointments"
            )
        
        # Clients cannot directly set status to confirmed or completed
        if 'status' in update_data and update_data['status'] not in [AppointmentStatus.CANCELLED]:
            raise HTTPException(
                status_code=403,
                detail="Clients can only cancel appointments, not confirm or complete them"
            )
            
    elif current_user.id == appointment.provider_id:
        # Providers can update status and limited other fields
        allowed_fields = {'status', 'description'}  # Providers can add notes
        provided_fields = set(update_data.keys())
        
        if not provided_fields.issubset(allowed_fields):
            forbidden_fields = provided_fields - allowed_fields
            raise HTTPException(
                status_code=400, 
                detail=f"Providers cannot update these fields: {', '.join(forbidden_fields)}"
            )
    else:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    appointment = crud_appointment.appointment.update(
        db=db, db_obj=appointment, obj_in=appointment_in, user_role=current_user.role
    )
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
    appointment = crud_appointment.appointment.get(db=db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.id != appointment.client_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if appointment.status != "pending":
        raise HTTPException(
            status_code=400, detail="Can only delete pending appointments"
        )

    crud_appointment.appointment.remove(db=db, id=appointment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/availability/{date}", response_model=List[TimeSlot])
def get_availability(
    *,
    db: Session = Depends(deps.get_db),
    date: str,
    provider_id: int = Query(..., description="ID of the provider"),
) -> Any:
    """
    Get available time slots for a specific date and provider
    """
    try:
        # Parse the date
        selected_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        # Don't allow appointments in the past
        if selected_date < datetime.now().date():
            raise HTTPException(
                status_code=400, detail="Cannot book appointments in the past"
            )
        
        # Verify provider exists and is a provider
        provider = db.query(User).filter(User.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if provider.role != UserRole.PROVIDER:
            raise HTTPException(status_code=400, detail="User is not a provider")
        
        # Generate time slots (9 AM to 5 PM, 30-minute intervals)
        slots = []
        start_time = time(9, 0)  # 9:00 AM
        end_time = time(17, 0)   # 5:00 PM
        slot_duration = timedelta(minutes=30)
        
        current_time = datetime.combine(selected_date, start_time)
        end_datetime = datetime.combine(selected_date, end_time)
        
        while current_time < end_datetime:
            slot_start = current_time.time()
            slot_end = (current_time + slot_duration).time()
            
            # Check if this slot conflicts with existing appointments
            slot_datetime = datetime.combine(selected_date, slot_start)
            slot_end_datetime = slot_datetime + slot_duration
            
            # Query for appointments that could overlap with this slot
            existing_appointments = db.query(AppointmentModel).filter(
                AppointmentModel.provider_id == provider_id,
                AppointmentModel.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
                func.date(AppointmentModel.date_time) == selected_date
            ).all()
            
            # Check for overlap with any existing appointment
            is_available = True
            for appointment in existing_appointments:
                appointment_start = appointment.date_time
                appointment_end = appointment_start + timedelta(minutes=appointment.duration_minutes)
                
                # Check if slot overlaps with this appointment
                if slot_datetime < appointment_end and slot_end_datetime > appointment_start:
                    is_available = False
                    break
            
            slots.append(TimeSlot(
                start=slot_start.strftime("%H:%M"),
                end=slot_end.strftime("%H:%M"),
                available=is_available
            ))
            
            current_time += slot_duration
        
        return slots
        
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
        )


@router.post("/validate-availability")
def validate_appointment_availability(
    *,
    db: Session = Depends(deps.get_db),
    provider_id: int = Query(...),
    date_time: str = Query(..., description="ISO datetime string"),
    duration_minutes: int = Query(30, description="Duration in minutes"),
) -> Any:
    """
    Validate if a specific time slot is available for booking
    Returns availability status and conflict details if any
    """
    try:
        # Parse the datetime
        appointment_datetime = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
        
        # Check if date is in the past
        from datetime import timezone
        if appointment_datetime < datetime.now(timezone.utc):
            return {
                "available": False,
                "reason": "Cannot book appointments in the past"
            }
        
        # Verify provider exists
        provider = db.query(User).filter(User.id == provider_id).first()
        if not provider or provider.role != UserRole.PROVIDER:
            return {
                "available": False,
                "reason": "Provider not found or invalid"
            }
        
        # Check for overlapping appointments
        appointment_start = appointment_datetime
        appointment_end = appointment_start + timedelta(minutes=duration_minutes)
        
        existing_appointments = db.query(AppointmentModel).filter(
            AppointmentModel.provider_id == provider_id,
            AppointmentModel.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            func.date(AppointmentModel.date_time) == appointment_start.date()
        ).all()
        
        for existing in existing_appointments:
            existing_start = existing.date_time
            existing_end = existing_start + timedelta(minutes=existing.duration_minutes)
            
            if appointment_start < existing_end and appointment_end > existing_start:
                return {
                    "available": False,
                    "reason": f"Conflicts with appointment '{existing.title}' from {existing_start.strftime('%H:%M')} to {existing_end.strftime('%H:%M')}",
                    "conflicting_appointment": {
                        "id": existing.id,
                        "title": existing.title,
                        "start_time": existing_start.isoformat(),
                        "end_time": existing_end.isoformat()
                    }
                }
        
        return {
            "available": True,
            "reason": "Time slot is available"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid datetime format: {str(e)}"
        )


@router.post("/{appointment_id}/confirm", response_model=Appointment)
def confirm_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Confirm an appointment (providers only)
    """
    appointment = crud_appointment.appointment.get(db=db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if current_user.id != appointment.provider_id:
        raise HTTPException(status_code=403, detail="Only the assigned provider can confirm appointments")
    
    appointment_update = AppointmentUpdate(status=AppointmentStatus.CONFIRMED)
    appointment = crud_appointment.appointment.update(
        db=db, db_obj=appointment, obj_in=appointment_update, user_role=current_user.role
    )
    return appointment


@router.post("/{appointment_id}/complete", response_model=Appointment)
def complete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Mark an appointment as completed (providers only)
    """
    appointment = crud_appointment.appointment.get(db=db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if current_user.id != appointment.provider_id:
        raise HTTPException(status_code=403, detail="Only the assigned provider can complete appointments")
    
    appointment_update = AppointmentUpdate(status=AppointmentStatus.COMPLETED)
    appointment = crud_appointment.appointment.update(
        db=db, db_obj=appointment, obj_in=appointment_update, user_role=current_user.role
    )
    return appointment


@router.post("/{appointment_id}/cancel", response_model=Appointment)
def cancel_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Cancel an appointment (both client and provider can cancel)
    """
    appointment = crud_appointment.appointment.get(db=db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if current_user.id not in [appointment.client_id, appointment.provider_id]:
        raise HTTPException(status_code=403, detail="Only client or provider can cancel appointments")
    
    appointment_update = AppointmentUpdate(status=AppointmentStatus.CANCELLED)
    appointment = crud_appointment.appointment.update(
        db=db, db_obj=appointment, obj_in=appointment_update, user_role=current_user.role
    )
    return appointment
