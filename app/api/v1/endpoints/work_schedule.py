from typing import List, Any, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User, UserRole
from app.schemas.work_schedule import (
    WorkSchedule, WorkScheduleCreate, WorkScheduleUpdate,
    ScheduleException, ScheduleExceptionCreate, ScheduleExceptionUpdate,
    ProviderSettings, ProviderSettingsCreate, ProviderSettingsUpdate,
    WeeklyScheduleResponse, ProviderAvailabilityResponse
)
from app.crud.crud_work_schedule import work_schedule_crud

router = APIRouter()


# ========== WORK SCHEDULES ==========

@router.post("/schedules", response_model=WorkSchedule)
def create_work_schedule(
    *,
    db: Session = Depends(deps.get_db),
    schedule_in: WorkScheduleCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a work schedule for a specific day.
    Only providers can create their own schedules.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403, 
            detail="Only providers can create work schedules"
        )
    
    if current_user.id != schedule_in.provider_id:
        raise HTTPException(
            status_code=403,
            detail="Can only create schedules for yourself"
        )
    
    return work_schedule_crud.create_work_schedule(db=db, obj_in=schedule_in)


@router.get("/schedules/{provider_id}", response_model=List[WorkSchedule])
def get_provider_work_schedules(
    *,
    db: Session = Depends(deps.get_db),
    provider_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get all work schedules for a provider.
    Providers can see their own schedules, clients can see any provider's schedules.
    """
    if current_user.role == UserRole.PROVIDER and current_user.id != provider_id:
        raise HTTPException(
            status_code=403,
            detail="Providers can only view their own schedules"
        )
    
    return work_schedule_crud.get_work_schedules(db=db, provider_id=provider_id)


@router.put("/schedules/{schedule_id}", response_model=WorkSchedule)
def update_work_schedule(
    *,
    db: Session = Depends(deps.get_db),
    schedule_id: int,
    schedule_in: WorkScheduleUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a work schedule.
    Only the schedule owner can update it.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403,
            detail="Only providers can update work schedules"
        )
    
    # TODO: Add validation to ensure the schedule belongs to the current user
    return work_schedule_crud.update_work_schedule(
        db=db, schedule_id=schedule_id, obj_in=schedule_in
    )


@router.delete("/schedules/{schedule_id}")
def delete_work_schedule(
    *,
    db: Session = Depends(deps.get_db),
    schedule_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a work schedule.
    Only the schedule owner can delete it.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403,
            detail="Only providers can delete work schedules"
        )
    
    # TODO: Add validation to ensure the schedule belongs to the current user
    work_schedule_crud.delete_work_schedule(db=db, schedule_id=schedule_id)
    return {"message": "Work schedule deleted successfully"}


# ========== SCHEDULE EXCEPTIONS ==========

@router.post("/exceptions", response_model=ScheduleException)
def create_schedule_exception(
    *,
    db: Session = Depends(deps.get_db),
    exception_in: ScheduleExceptionCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a schedule exception (vacation, day off, custom hours).
    Only providers can create their own exceptions.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403,
            detail="Only providers can create schedule exceptions"
        )
    
    if current_user.id != exception_in.provider_id:
        raise HTTPException(
            status_code=403,
            detail="Can only create exceptions for yourself"
        )
    
    return work_schedule_crud.create_schedule_exception(db=db, obj_in=exception_in)


@router.get("/exceptions/{provider_id}", response_model=List[ScheduleException])
def get_schedule_exceptions(
    *,
    db: Session = Depends(deps.get_db),
    provider_id: int,
    start_date: Optional[date] = Query(None, description="Filter from this date"),
    end_date: Optional[date] = Query(None, description="Filter until this date"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get schedule exceptions for a provider.
    """
    if current_user.role == UserRole.PROVIDER and current_user.id != provider_id:
        raise HTTPException(
            status_code=403,
            detail="Providers can only view their own exceptions"
        )
    
    return work_schedule_crud.get_schedule_exceptions(
        db=db, provider_id=provider_id, start_date=start_date, end_date=end_date
    )


@router.put("/exceptions/{exception_id}", response_model=ScheduleException)
def update_schedule_exception(
    *,
    db: Session = Depends(deps.get_db),
    exception_id: int,
    exception_in: ScheduleExceptionUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a schedule exception.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403,
            detail="Only providers can update schedule exceptions"
        )
    
    # TODO: Add validation to ensure the exception belongs to the current user
    return work_schedule_crud.update_schedule_exception(
        db=db, exception_id=exception_id, obj_in=exception_in
    )


@router.delete("/exceptions/{exception_id}")
def delete_schedule_exception(
    *,
    db: Session = Depends(deps.get_db),
    exception_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a schedule exception.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403,
            detail="Only providers can delete schedule exceptions"
        )
    
    # TODO: Add validation to ensure the exception belongs to the current user
    work_schedule_crud.delete_schedule_exception(db=db, exception_id=exception_id)
    return {"message": "Schedule exception deleted successfully"}


# ========== PROVIDER SETTINGS ==========

@router.post("/settings", response_model=ProviderSettings)
def create_or_update_provider_settings(
    *,
    db: Session = Depends(deps.get_db),
    settings_in: ProviderSettingsCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create or update provider settings.
    """
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=403,
            detail="Only providers can manage settings"
        )
    
    if current_user.id != settings_in.provider_id:
        raise HTTPException(
            status_code=403,
            detail="Can only manage your own settings"
        )
    
    return work_schedule_crud.create_or_update_provider_settings(db=db, obj_in=settings_in)


@router.get("/settings/{provider_id}", response_model=ProviderSettings)
def get_provider_settings(
    *,
    db: Session = Depends(deps.get_db),
    provider_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get provider settings.
    """
    settings = work_schedule_crud.get_provider_settings(db=db, provider_id=provider_id)
    if not settings:
        raise HTTPException(
            status_code=404,
            detail="Provider settings not found"
        )
    
    return settings


# ========== AVAILABILITY ==========

@router.get("/availability/{provider_id}/{date}", response_model=dict)
def get_provider_availability(
    *,
    db: Session = Depends(deps.get_db),
    provider_id: int,
    date: date,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get provider availability for a specific date.
    Returns available time slots considering work schedules, exceptions, and existing appointments.
    """
    availability = work_schedule_crud.get_provider_availability_for_date(
        db=db, provider_id=provider_id, target_date=date
    )
    
    return {
        "provider_id": provider_id,
        "date": date,
        **availability
    }


@router.get("/weekly-schedule/{provider_id}", response_model=dict)
def get_weekly_schedule(
    *,
    db: Session = Depends(deps.get_db),
    provider_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get complete weekly schedule for a provider including settings.
    """
    schedules = work_schedule_crud.get_work_schedules(db=db, provider_id=provider_id)
    settings = work_schedule_crud.get_provider_settings(db=db, provider_id=provider_id)
    
    return {
        "provider_id": provider_id,
        "schedules": schedules,
        "settings": settings
    }