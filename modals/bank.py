from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from modals.currency import Currency


class Base(DeclarativeBase):
    pass


class Bank(Base):
    __tablename__ = "bank"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    currency_id: Mapped[int] = mapped_column(Integer, ForeignKey(Currency.id))
    amount: Mapped[int] = mapped_column(Integer)
