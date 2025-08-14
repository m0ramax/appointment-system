from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, time, timedelta, timezone
from typing import List, Optional, Dict, Tuple
from fastapi import HTTPException, status

from app.models.work_schedule import WorkSchedule, ScheduleException, ProviderSettings, DayOfWeek, ExceptionType
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.work_schedule import (
    WorkScheduleCreate, WorkScheduleUpdate,
    ScheduleExceptionCreate, ScheduleExceptionUpdate,
    ProviderSettingsCreate, ProviderSettingsUpdate
)


class CRUDWorkSchedule:
    
    # ========== WORK SCHEDULES ==========
    
    def create_work_schedule(self, db: Session, *, obj_in: WorkScheduleCreate) -> WorkSchedule:
        """Crear un horario de trabajo para un día específico"""
        # Verificar que no exista ya un horario para este proveedor y día
        existing = db.query(WorkSchedule).filter(
            WorkSchedule.provider_id == obj_in.provider_id,
            WorkSchedule.day_of_week == obj_in.day_of_week
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Work schedule for {obj_in.day_of_week.name} already exists"
            )
        
        db_obj = WorkSchedule(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_work_schedules(self, db: Session, provider_id: int) -> List[WorkSchedule]:
        """Obtener todos los horarios de trabajo de un proveedor"""
        return db.query(WorkSchedule).filter(
            WorkSchedule.provider_id == provider_id,
            WorkSchedule.is_active == True
        ).order_by(WorkSchedule.day_of_week).all()
    
    def update_work_schedule(
        self, db: Session, *, schedule_id: int, obj_in: WorkScheduleUpdate
    ) -> WorkSchedule:
        """Actualizar un horario de trabajo existente"""
        db_obj = db.query(WorkSchedule).filter(WorkSchedule.id == schedule_id).first()
        if not db_obj:
            raise HTTPException(status_code=404, detail="Work schedule not found")
        
        update_data = obj_in.model_dump(exclude_unset=True)
        for field in update_data:
            setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete_work_schedule(self, db: Session, *, schedule_id: int) -> bool:
        """Eliminar un horario de trabajo"""
        db_obj = db.query(WorkSchedule).filter(WorkSchedule.id == schedule_id).first()
        if not db_obj:
            raise HTTPException(status_code=404, detail="Work schedule not found")
        
        db.delete(db_obj)
        db.commit()
        return True
    
    # ========== SCHEDULE EXCEPTIONS ==========
    
    def create_schedule_exception(
        self, db: Session, *, obj_in: ScheduleExceptionCreate
    ) -> ScheduleException:
        """Crear una excepción de horario"""
        # Verificar que no exista ya una excepción para esta fecha
        existing = db.query(ScheduleException).filter(
            ScheduleException.provider_id == obj_in.provider_id,
            ScheduleException.date == obj_in.date
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Exception for {obj_in.date} already exists"
            )
        
        db_obj = ScheduleException(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_schedule_exceptions(
        self, db: Session, provider_id: int, start_date: date = None, end_date: date = None
    ) -> List[ScheduleException]:
        """Obtener excepciones de horario de un proveedor"""
        query = db.query(ScheduleException).filter(
            ScheduleException.provider_id == provider_id
        )
        
        if start_date:
            query = query.filter(ScheduleException.date >= start_date)
        if end_date:
            query = query.filter(ScheduleException.date <= end_date)
        
        return query.order_by(ScheduleException.date).all()
    
    def update_schedule_exception(
        self, db: Session, *, exception_id: int, obj_in: ScheduleExceptionUpdate
    ) -> ScheduleException:
        """Actualizar una excepción de horario"""
        db_obj = db.query(ScheduleException).filter(ScheduleException.id == exception_id).first()
        if not db_obj:
            raise HTTPException(status_code=404, detail="Schedule exception not found")
        
        update_data = obj_in.model_dump(exclude_unset=True)
        for field in update_data:
            setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete_schedule_exception(self, db: Session, *, exception_id: int) -> bool:
        """Eliminar una excepción de horario"""
        db_obj = db.query(ScheduleException).filter(ScheduleException.id == exception_id).first()
        if not db_obj:
            raise HTTPException(status_code=404, detail="Schedule exception not found")
        
        db.delete(db_obj)
        db.commit()
        return True
    
    # ========== PROVIDER SETTINGS ==========
    
    def create_or_update_provider_settings(
        self, db: Session, *, obj_in: ProviderSettingsCreate
    ) -> ProviderSettings:
        """Crear o actualizar configuración de proveedor"""
        existing = db.query(ProviderSettings).filter(
            ProviderSettings.provider_id == obj_in.provider_id
        ).first()
        
        if existing:
            # Actualizar existente
            update_data = obj_in.model_dump(exclude={"provider_id"})
            for field in update_data:
                setattr(existing, field, update_data[field])
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Crear nuevo
            db_obj = ProviderSettings(**obj_in.model_dump())
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
    
    def get_provider_settings(self, db: Session, provider_id: int) -> Optional[ProviderSettings]:
        """Obtener configuración de un proveedor"""
        return db.query(ProviderSettings).filter(
            ProviderSettings.provider_id == provider_id
        ).first()
    
    # ========== AVAILABILITY LOGIC ==========
    
    def get_provider_availability_for_date(
        self, db: Session, provider_id: int, target_date: date
    ) -> Dict:
        """
        Obtener disponibilidad completa de un proveedor para una fecha específica
        Considera horarios regulares, excepciones y citas existentes
        """
        # Obtener día de la semana (0=domingo, 1=lunes, etc.)
        day_of_week = DayOfWeek(target_date.weekday() + 1 if target_date.weekday() < 6 else 0)
        
        # 1. Verificar si hay una excepción para esta fecha
        exception = db.query(ScheduleException).filter(
            ScheduleException.provider_id == provider_id,
            ScheduleException.date == target_date
        ).first()
        
        if exception:
            if exception.exception_type in [ExceptionType.DAY_OFF, ExceptionType.VACATION, ExceptionType.HOLIDAY]:
                return {
                    "is_available": False,
                    "reason": f"{exception.exception_type.value}: {exception.reason or 'No reason provided'}",
                    "available_slots": []
                }
            elif exception.exception_type == ExceptionType.CUSTOM_HOURS:
                # Usar horario personalizado
                start_time = exception.start_time
                end_time = exception.end_time
                slot_duration = exception.slot_duration_minutes or 30
        else:
            # 2. Usar horario regular del día de la semana
            regular_schedule = db.query(WorkSchedule).filter(
                WorkSchedule.provider_id == provider_id,
                WorkSchedule.day_of_week == day_of_week,
                WorkSchedule.is_active == True
            ).first()
            
            if not regular_schedule:
                return {
                    "is_available": False,
                    "reason": f"No work schedule configured for {day_of_week.name}",
                    "available_slots": []
                }
            
            start_time = regular_schedule.start_time
            end_time = regular_schedule.end_time
            slot_duration = regular_schedule.slot_duration_minutes
            break_start = regular_schedule.break_start
            break_end = regular_schedule.break_end
        
        # 3. Generar slots disponibles
        slots = self._generate_time_slots(
            start_time=start_time,
            end_time=end_time,
            slot_duration=slot_duration,
            break_start=getattr(exception, 'break_start', None) if exception else regular_schedule.break_start,
            break_end=getattr(exception, 'break_end', None) if exception else regular_schedule.break_end
        )
        
        # 4. Filtrar slots ya ocupados por citas existentes
        existing_appointments = db.query(Appointment).filter(
            Appointment.provider_id == provider_id,
            func.date(Appointment.date_time) == target_date,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).all()
        
        available_slots = []
        for slot in slots:
            slot_datetime = datetime.combine(target_date, slot["start_time"])
            slot_end_datetime = datetime.combine(target_date, slot["end_time"])
            
            # Verificar si el slot se superpone con alguna cita existente
            is_occupied = False
            for appointment in existing_appointments:
                appointment_end = appointment.date_time + timedelta(minutes=appointment.duration_minutes)
                
                # Verificar superposición
                if (slot_datetime < appointment_end and slot_end_datetime > appointment.date_time):
                    is_occupied = True
                    break
            
            if not is_occupied:
                available_slots.append({
                    "start": slot["start_time"].strftime("%H:%M"),
                    "end": slot["end_time"].strftime("%H:%M"),
                    "available": True
                })
        
        return {
            "is_available": len(available_slots) > 0,
            "reason": "Available slots found" if available_slots else "All slots occupied",
            "available_slots": available_slots
        }
    
    def _generate_time_slots(
        self, 
        start_time: time, 
        end_time: time, 
        slot_duration: int,
        break_start: Optional[time] = None,
        break_end: Optional[time] = None
    ) -> List[Dict]:
        """Generar slots de tiempo basado en horario y duración"""
        slots = []
        current_time = datetime.combine(date.today(), start_time)
        end_datetime = datetime.combine(date.today(), end_time)
        slot_delta = timedelta(minutes=slot_duration)
        
        # Convertir breaks a datetime si existen
        break_start_dt = datetime.combine(date.today(), break_start) if break_start else None
        break_end_dt = datetime.combine(date.today(), break_end) if break_end else None
        
        while current_time + slot_delta <= end_datetime:
            slot_end = current_time + slot_delta
            
            # Verificar si el slot se superpone con el horario de descanso
            if break_start_dt and break_end_dt:
                if not (slot_end <= break_start_dt or current_time >= break_end_dt):
                    # Skip this slot, it overlaps with break time
                    current_time += slot_delta
                    continue
            
            slots.append({
                "start_time": current_time.time(),
                "end_time": slot_end.time()
            })
            
            current_time += slot_delta
        
        return slots


# Instancia global del CRUD
work_schedule_crud = CRUDWorkSchedule()