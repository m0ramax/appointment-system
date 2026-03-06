from datetime import datetime, timedelta

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User, UserRole


def get_or_create_user(db, email: str, password: str, role: UserRole) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def appointment_exists(
    db, client_id: int, provider_id: int, date_time: datetime
) -> bool:
    return (
        db.query(Appointment)
        .filter(
            Appointment.client_id == client_id,
            Appointment.provider_id == provider_id,
            Appointment.date_time == date_time,
        )
        .first()
        is not None
    )


def create_appointment(
    db,
    title: str,
    description: str,
    date_time: datetime,
    duration_minutes: int,
    status: AppointmentStatus,
    client_id: int,
    provider_id: int,
) -> None:
    if appointment_exists(db, client_id, provider_id, date_time):
        return

    appt = Appointment(
        title=title,
        description=description,
        date_time=date_time,
        duration_minutes=duration_minutes,
        status=status,
        client_id=client_id,
        provider_id=provider_id,
    )
    db.add(appt)
    db.commit()


def main():
    db = SessionLocal()
    try:
        provider = get_or_create_user(
            db, "provider.demo@local.dev", "DemoPass123!", UserRole.PROVIDER
        )
        client_1 = get_or_create_user(
            db, "client.one@local.dev", "DemoPass123!", UserRole.CLIENT
        )
        client_2 = get_or_create_user(
            db, "client.two@local.dev", "DemoPass123!", UserRole.CLIENT
        )

        base = datetime.now().replace(second=0, microsecond=0) + timedelta(days=1)

        create_appointment(
            db=db,
            title="Consulta Inicial",
            description="Primera consulta de prueba",
            date_time=base.replace(hour=10, minute=0),
            duration_minutes=30,
            status=AppointmentStatus.PENDING,
            client_id=client_1.id,
            provider_id=provider.id,
        )
        create_appointment(
            db=db,
            title="Seguimiento",
            description="Control Semanal",
            date_time=base.replace(hour=11, minute=0),
            duration_minutes=45,
            status=AppointmentStatus.CONFIRMED,
            client_id=client_2.id,
            provider_id=provider.id,
        )

        print("---------------")
        print("Seed completado")
        print("Usuarios Demo:")
        print("   provider.demo@local.dev / DemoPass123!")
        print("   client.one@local.dev / DemoPass123!")
        print("   client.two@local.dev / DemoPass123!")
        print("------------")
    finally:
        db.close()


if __name__ == "__main__":
    main()
