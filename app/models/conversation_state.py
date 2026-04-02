from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.sql import func
from .user import Base


class ConversationState(Base):
    __tablename__ = "conversation_states"

    phone = Column(String, primary_key=True)
    state = Column(String, nullable=False, default="INICIO")
    context = Column(JSON, nullable=True, default=dict)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self):
        return f"<ConversationState phone={self.phone} state={self.state}>"
