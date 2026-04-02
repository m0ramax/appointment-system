from .user import User
from .appointment import Appointment
from .work_schedule import WorkSchedule, ScheduleException, ProviderSettings
from .conversation_state import ConversationState

# Esto asegura que ambas clases estén disponibles cuando se necesiten
__all__ = ["User", "Appointment", "WorkSchedule", "ScheduleException", "ProviderSettings", "ConversationState"]
