from typing import Optional

from schemas import DebateConfig, PanelConfig
from sqlmodel import Session

from routes.common import champion_for_debate, members_from_config


def _champion_for_debate(session: Session, debate_id: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    return champion_for_debate(session, debate_id)


def _members_from_config(config: DebateConfig, panel: PanelConfig | None = None) -> list[dict[str, str]]:
    return members_from_config(config, panel)
