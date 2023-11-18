from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    dice_win: Mapped[int] = mapped_column(Integer, nullable=True)
    min_bet: Mapped[int] = mapped_column(Integer, default=10_000)
    max_bet: Mapped[int] = mapped_column(Integer, default=50_000)
