from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    CLIENT = "client"
    PROVIDER = "provider"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CLIENT)

    # Relaciones con citas usando strings para evitar importaciones circulares
    client_appointments = relationship(
        "Appointment",
        primaryjoin="User.id == Appointment.client_id",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    provider_appointments = relationship(
        "Appointment",
        primaryjoin="User.id == Appointment.provider_id",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.email}>"
