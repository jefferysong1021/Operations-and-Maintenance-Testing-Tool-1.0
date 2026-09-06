from contextlib import contextmanager
from pathlib import Path
import os

from sqlalchemy import String, create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parent
configured_database_url = os.getenv("OPS_TEST_DATABASE_URL")
configured_db_path = os.getenv("OPS_TEST_DB_PATH")
DB_PATH = Path(configured_db_path) if configured_db_path else PROJECT_ROOT / "ops_test.db"
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH

DATABASE_URL = configured_database_url or f"sqlite:///{DB_PATH.as_posix()}"
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


class Base(DeclarativeBase):
    pass


class ServiceCheck(Base):
    __tablename__ = "service_checks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    checked_at: Mapped[str] = mapped_column(String(100), nullable=False)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@contextmanager
def get_db_connection():
    session: Session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database():
    Base.metadata.create_all(bind=engine)


def record_check(status: str, checked_at: str) -> bool:
    try:
        with get_db_connection() as session:
            session.add(ServiceCheck(status=status, checked_at=checked_at))
        return True
    except SQLAlchemyError:
        return False


def fetch_checks(limit: int) -> list[dict[str, object]]:
    with get_db_connection() as session:
        rows = session.execute(
            select(ServiceCheck)
            .order_by(ServiceCheck.id.desc())
            .limit(limit)
        ).scalars().all()

    return [
        {
            "id": row.id,
            "status": row.status,
            "checked_at": row.checked_at,
        }
        for row in rows
    ]
