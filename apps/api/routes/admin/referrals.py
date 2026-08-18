from __future__ import annotations

from datetime import timedelta

from auth import get_current_admin
from billing.models import ReferralAttribution
from deps import get_session
from fastapi import APIRouter, Depends
from models import User, utcnow
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()


def build_referral_metrics(session: Session) -> dict:
    """Build the canonical privacy-preserving public-share funnel metrics."""
    now = utcnow()
    month_ago = now - timedelta(days=30)

    issued_30d = int(
        session.exec(
            select(func.count(ReferralAttribution.id)).where(
                ReferralAttribution.created_at >= month_ago
            )
        ).one()
        or 0
    )
    visited_30d = int(
        session.exec(
            select(func.count(ReferralAttribution.id))
            .where(ReferralAttribution.created_at >= month_ago)
            .where(ReferralAttribution.visited_at.is_not(None))
        ).one()
        or 0
    )
    claimed_30d = int(
        session.exec(
            select(func.count(ReferralAttribution.id))
            .where(ReferralAttribution.created_at >= month_ago)
            .where(ReferralAttribution.claimed_at.is_not(None))
        ).one()
        or 0
    )
    total_views_30d = int(
        session.exec(
            select(func.sum(ReferralAttribution.view_count)).where(
                ReferralAttribution.created_at >= month_ago
            )
        ).one()
        or 0
    )
    shared_artifacts_30d = int(
        session.exec(
            select(func.count(func.distinct(ReferralAttribution.debate_id))).where(
                ReferralAttribution.created_at >= month_ago
            )
        ).one()
        or 0
    )

    conversion_rate = claimed_30d / visited_30d * 100.0 if visited_30d else 0.0
    visit_rate = visited_30d / issued_30d * 100.0 if issued_30d else 0.0

    return {
        "window_days": 30,
        "issued_links": issued_30d,
        "visited_links": visited_30d,
        "claimed_signups": claimed_30d,
        "total_views": total_views_30d,
        "shared_artifacts": shared_artifacts_30d,
        "visit_rate": visit_rate,
        "conversion_rate": conversion_rate,
        "attribution_method": "sha256_referral_token",
        "stores_raw_token": False,
        "uses_visitor_ip": False,
        "definitions": {
            "issued_links": "Referral tokens created for copied public decision links in the last 30 days.",
            "visited_links": "Unique issued tokens with at least one accepted public visit.",
            "claimed_signups": "Unique referral tokens claimed by an authenticated user.",
            "conversion_rate": "claimed_signups / visited_links; token-grain numerator and denominator.",
        },
    }


@router.get("/referral-metrics")
def admin_referral_metrics(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Return privacy-preserving public-share funnel metrics.

    The denominator is unique referral tokens with a recorded visit; numerator
    is unique tokens claimed by an authenticated user. No visitor IP is stored or
    used for this canonical conversion metric.
    """
    return build_referral_metrics(session)
