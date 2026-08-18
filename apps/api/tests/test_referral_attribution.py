import hashlib
from datetime import timedelta

from billing.models import ReferralAttribution
from models import Debate, User, utcnow
from routes.admin.referrals import admin_referral_metrics
from services.account_erasure import erase_user_account
from services.referrals import claim_referral, issue_referral_token, record_referral_visit
from sqlmodel import Session, select


def _user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="hashed", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _debate(session: Session, owner: User, debate_id: str) -> Debate:
    debate = Debate(
        id=debate_id,
        prompt="Referral test decision",
        status="completed",
        config={"is_public": True},
        user_id=owner.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(debate)
    session.commit()
    return debate


def test_referral_stores_only_hash_and_tracks_visit_claim(db_session: Session):
    owner = _user(db_session, "ref-owner@example.com")
    visitor = _user(db_session, "ref-visitor@example.com")
    debate = _debate(db_session, owner, "ref-debate-1")

    token, row = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    db_session.commit()
    db_session.refresh(row)

    assert token != row.token_hash
    assert row.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in row.token_hash
    assert row.view_count == 0

    assert record_referral_visit(db_session, token=token) is True
    assert record_referral_visit(db_session, token=token) is True
    db_session.commit()
    db_session.expire_all()

    persisted = db_session.get(ReferralAttribution, row.id)
    assert persisted is not None
    assert persisted.view_count == 2
    assert persisted.visited_at is not None
    assert persisted.last_visited_at is not None

    assert claim_referral(db_session, token=token, user_id=visitor.id) is True
    db_session.commit()
    db_session.expire_all()
    persisted = db_session.get(ReferralAttribution, row.id)
    assert persisted is not None
    assert persisted.claimed_by_user_id == visitor.id
    assert persisted.claimed_at is not None

    # Same-user retry is idempotent; another user cannot steal the claim.
    assert claim_referral(db_session, token=token, user_id=visitor.id) is True
    other = _user(db_session, "ref-other@example.com")
    assert claim_referral(db_session, token=token, user_id=other.id) is False


def test_claim_before_visit_beacon_counts_one_implicit_visit(db_session: Session):
    owner = _user(db_session, "ref-race-owner@example.com")
    visitor = _user(db_session, "ref-race-visitor@example.com")
    debate = _debate(db_session, owner, "ref-debate-race")
    token, row = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    db_session.commit()

    assert claim_referral(db_session, token=token, user_id=visitor.id) is True
    db_session.commit()
    db_session.expire_all()

    persisted = db_session.get(ReferralAttribution, row.id)
    assert persisted is not None
    assert persisted.view_count == 1
    assert persisted.visited_at is not None
    assert persisted.claimed_by_user_id == visitor.id


def test_invalid_or_expired_referral_is_not_accepted(db_session: Session):
    owner = _user(db_session, "ref-exp-owner@example.com")
    debate = _debate(db_session, owner, "ref-debate-expired")
    token, row = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    row.expires_at = utcnow() - timedelta(seconds=1)
    db_session.add(row)
    db_session.commit()

    assert record_referral_visit(db_session, token="not-a-real-token") is False
    assert record_referral_visit(db_session, token=token) is False
    assert claim_referral(db_session, token=token, user_id=owner.id) is False


def test_referral_metrics_use_token_grain_not_ip(db_session: Session):
    admin = _user(db_session, "ref-metrics-admin@example.com")
    owner = _user(db_session, "ref-metrics-owner@example.com")
    claimed_user = _user(db_session, "ref-metrics-claim@example.com")
    debate = _debate(db_session, owner, "ref-debate-metrics")

    visited_token, _ = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    unvisited_token, _ = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    assert unvisited_token != visited_token
    record_referral_visit(db_session, token=visited_token)
    claim_referral(db_session, token=visited_token, user_id=claimed_user.id)
    db_session.commit()

    metrics = admin_referral_metrics(session=db_session, _=admin)
    assert metrics["issued_links"] == 2
    assert metrics["visited_links"] == 1
    assert metrics["claimed_signups"] == 1
    assert metrics["conversion_rate"] == 100.0
    assert metrics["uses_visitor_ip"] is False
    assert metrics["stores_raw_token"] is False


def test_account_erasure_detaches_referral_user_links(db_session: Session):
    owner = _user(db_session, "ref-erase-owner@example.com")
    visitor = _user(db_session, "ref-erase-visitor@example.com")
    debate = _debate(db_session, owner, "ref-debate-erasure")
    token, row = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    claim_referral(db_session, token=token, user_id=visitor.id)
    db_session.commit()
    row_id = row.id

    erase_user_account(db_session, visitor)
    db_session.commit()
    db_session.expire_all()
    persisted = db_session.get(ReferralAttribution, row_id)
    assert persisted is not None
    assert persisted.claimed_by_user_id is None
    assert persisted.claimed_at is not None

    erase_user_account(db_session, owner)
    db_session.commit()
    db_session.expire_all()
    persisted = db_session.get(ReferralAttribution, row_id)
    assert persisted is not None
    assert persisted.created_by_user_id is None
