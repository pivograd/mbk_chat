from sqlalchemy import String, Integer
from sqlalchemy.orm import mapped_column

from db.models.base import Base


class BxContactCwMap(Base):
    __tablename__ = "bx_contact_cw_map"
    bx_portal = mapped_column(String(255), primary_key=True)
    bx_contact_id = mapped_column(Integer, primary_key=True)
    cw_contact_id = mapped_column(Integer, nullable=False)
    identifier = mapped_column(String(64), nullable=False)  # нормализованный телефон без '+'
