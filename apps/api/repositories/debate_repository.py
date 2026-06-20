from typing import List, Optional

from models import Debate
from sqlmodel import Session, select


class DebateRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, debate_id: str) -> Optional[Debate]:
        return self.session.get(Debate, debate_id)

    def list_by_user_id(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Debate]:
        statement = (
            select(Debate)
            .where(Debate.user_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def create(self, debate: Debate) -> Debate:
        self.session.add(debate)
        self.session.commit()
        self.session.refresh(debate)
        return debate

    def update(self, debate: Debate) -> Debate:
        self.session.add(debate)
        self.session.commit()
        self.session.refresh(debate)
        return debate
