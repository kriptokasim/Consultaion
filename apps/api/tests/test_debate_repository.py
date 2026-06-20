import uuid

from models import Debate, User
from repositories.debate_repository import DebateRepository
from sqlmodel import Session


def test_debate_repository_crud(db_session: Session):
    # 1. Create a dummy user first
    user = User(email="repo_test@example.com", password_hash="hashed_password", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    repo = DebateRepository(db_session)
    
    # 2. Create debate
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Test prompt",
        status="pending",
        user_id=user.id,
        config={}
    )
    created = repo.create(debate)
    assert created.id is not None
    assert created.prompt == "Test prompt"

    # 3. Get debate
    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.prompt == "Test prompt"

    # 4. List debates
    debates_list = repo.list_by_user_id(user.id)
    assert len(debates_list) == 1
    assert debates_list[0].id == created.id

    # 5. Update debate
    created.status = "running"
    updated = repo.update(created)
    assert updated.status == "running"
