from sqlalchemy.orm import Session

from db.models import PoiModel


class PoiRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_city(self, city: str) -> list[PoiModel]:
        return self.db.query(PoiModel).filter(PoiModel.city == city).all()
