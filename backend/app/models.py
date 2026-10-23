from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    # 并发写入时别立刻报 locked，等一会儿（配合下面的 busy_timeout）
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - 只在连库时跑
    """WAL + busy_timeout：读写不互相阻塞，写写冲突时排队而不是直接抛 500。"""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=15000")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    """SQLite 存的是 naive datetime，序列化时补上 UTC 时区，
    否则前端会把它当本地时间，显示差 8 小时。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(256))
    yuanbao: Mapped[int] = mapped_column(Integer, default=settings.INITIAL_YUANBAO)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class InventoryItem(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_user_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))  # item / hero / skin
    rarity: Mapped[str] = mapped_column(String(16))
    qty: Mapped[int] = mapped_column(Integer, default=0)
    first_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PullRecord(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(16), index=True)  # box / hero / skin
    box_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    rarity: Mapped[str] = mapped_column(String(16), index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    # 本条记录代表的抽取次数：一次开盒产出 1 件物品，但物品可能带数量（如菜篮子*2），
    # 因此 qty（物品数量）与 pulls（抽取次数）必须分开统计。
    pulls: Mapped[int] = mapped_column(Integer, default=1)
    cost: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class PalaceState(Base):
    """天宫宝库的按期进度：幸运值、累计抽数、中奖次数（每期独立）。"""

    __tablename__ = "palace_state"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    period: Mapped[str] = mapped_column(String(32), primary_key=True, default="")
    luck: Mapped[int] = mapped_column(Integer, default=0)
    pulls: Mapped[int] = mapped_column(Integer, default=0)
    jackpots: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CorridorState(Base):
    """梦之回廊的按期进度：已点亮碎片、已领取连线、累计抽数（每期独立）。

    fragments / lines 存 JSON 数组字符串（SQLite 不必为此单开两张表）。
    """

    __tablename__ = "corridor_state"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    period: Mapped[str] = mapped_column(String(32), primary_key=True, default="")
    fragments: Mapped[str] = mapped_column(Text, default="[]")
    lines: Mapped[str] = mapped_column(Text, default="[]")
    pulls: Mapped[int] = mapped_column(Integer, default=0)
    finished: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
