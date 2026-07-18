import uuid

import pytest
from fastapi import HTTPException
from models import ConversationVote, Debate, Message, User
from routes.votes import VoteCreate, create_or_update_vote, get_vote_summary
from sqlmodel import select


@pytest.fixture
def conversation_v2(monkeypatch):
    from routes import votes

    monkeypatch.setattr(votes.settings, "ENABLE_CONVERSATION_V2", True)


def _seed_conversation(session, *, owner: User, is_public: bool = False):
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="vote target",
        status="completed",
        user_id=owner.id,
        config={"is_public": is_public},
    )
    session.add(debate)
    session.flush()
    message = Message(
        debate_id=debate.id,
        round_index=1,
        role="assistant",
        content="candidate",
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return debate, message


def test_vote_is_authenticated_idempotent_and_target_scoped(db_session, conversation_v2):
    owner = User(
        id=str(uuid.uuid4()),
        email=f"vote-owner-{uuid.uuid4().hex}@example.com",
        password_hash="hash",
    )
    db_session.add(owner)
    db_session.flush()
    debate, message = _seed_conversation(db_session, owner=owner)
    payload = VoteCreate(
        conversation_id=debate.id,
        message_id=str(message.id),
        vote=1,
    )

    first = create_or_update_vote(payload, session=db_session, current_user=owner)
    second = create_or_update_vote(
        payload.model_copy(update={"vote": -1}),
        session=db_session,
        current_user=owner,
    )

    assert first.action == "created"
    assert second.action == "updated"
    votes = db_session.exec(select(ConversationVote)).all()
    assert len(votes) == 1
    assert votes[0].user_id == owner.id
    assert votes[0].vote == -1


def test_vote_rejects_message_from_another_conversation(db_session, conversation_v2):
    owner = User(
        id=str(uuid.uuid4()),
        email=f"vote-owner-{uuid.uuid4().hex}@example.com",
        password_hash="hash",
    )
    db_session.add(owner)
    db_session.flush()
    first_debate, _ = _seed_conversation(db_session, owner=owner)
    _, second_message = _seed_conversation(db_session, owner=owner)

    with pytest.raises(HTTPException) as exc_info:
        create_or_update_vote(
            VoteCreate(
                conversation_id=first_debate.id,
                message_id=str(second_message.id),
                vote=1,
            ),
            session=db_session,
            current_user=owner,
        )
    assert exc_info.value.status_code == 404


def test_private_vote_summary_requires_access(db_session, conversation_v2):
    owner = User(
        id=str(uuid.uuid4()),
        email=f"vote-owner-{uuid.uuid4().hex}@example.com",
        password_hash="hash",
    )
    stranger = User(
        id=str(uuid.uuid4()),
        email=f"vote-stranger-{uuid.uuid4().hex}@example.com",
        password_hash="hash",
    )
    db_session.add(owner)
    db_session.add(stranger)
    db_session.flush()
    debate, _ = _seed_conversation(db_session, owner=owner)

    with pytest.raises(HTTPException) as exc_info:
        get_vote_summary(conversation_id=debate.id, session=db_session, current_user=stranger)
    assert exc_info.value.status_code == 404
