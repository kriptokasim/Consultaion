#!/usr/bin/env python3
"""Historical Response Integrity Audit and Safe Repair (FH122).

Audits completed Runs to identify those lacking Message rows and safely
recovers content from existing durable storage.

Usage:
    python scripts/audit_historical_responses.py --dry-run
    python scripts/audit_historical_responses.py --debate-id <ID> --repair --confirm <ID>
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Ensure the api/ directory is on sys.path so sibling packages resolve.
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from sqlmodel import Session, select, func  # noqa: E402  # isort: skip
from database import session_scope  # noqa: E402  # isort: skip
from models import AuditLog, Debate, Message  # noqa: E402  # isort: skip

logger = logging.getLogger(__name__)

RESPONSE_ROLES = {
    "arena_response",
    "seat",
    "delegate",
    "candidate",
    "revised",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expected_model_count(debate: Debate) -> int:
    """Best-effort count of expected models for a debate."""
    final_meta = debate.final_meta or {}
    total = final_meta.get("total_count")
    if isinstance(total, int) and total > 0:
        return total

    config = debate.config or {}
    models = config.get("models") or []
    if isinstance(models, list) and models:
        return len(models)

    panel = debate.panel_config or {}
    panel_models = panel.get("models") or panel.get("panel") or []
    if isinstance(panel_models, list) and panel_models:
        return len(panel_models)

    return 0


def classify_debate(session: Session, debate: Debate) -> Dict[str, Any]:
    """Classify a debate based on its response integrity."""
    debate_id = debate.id

    # Count responses (canonical roles)
    response_count = session.exec(
        select(func.count(Message.id)).where(
            Message.debate_id == debate_id,
            Message.role.in_(RESPONSE_ROLES),
        )
    ).one()

    expected_count = _expected_model_count(debate)

    # Count all messages
    total_messages = session.exec(
        select(func.count(Message.id)).where(Message.debate_id == debate_id)
    ).one()

    # Check for event rows (non-response roles with content)
    event_count = session.exec(
        select(func.count(Message.id)).where(
            Message.debate_id == debate_id,
            Message.role.notin_(RESPONSE_ROLES),
        )
    ).one()

    # Check for synthesis content
    has_synthesis = False
    if debate.final_meta:
        has_synthesis = bool(debate.final_meta.get("synthesis_report"))

    # Check for final content
    has_final_content = debate.final_content is not None

    # Check for duplicate responses
    all_responses = session.exec(
        select(Message).where(
            Message.debate_id == debate_id,
            Message.role.in_(RESPONSE_ROLES),
        )
    ).all()
    
    seen_model_ids = {}
    duplicate_response_count = 0
    for msg in all_responses:
        meta = msg.meta or {}
        model_id = meta.get("model_id", msg.persona)
        if model_id in seen_model_ids:
            duplicate_response_count += 1
        else:
            seen_model_ids[model_id] = msg.id

    # Check for invalid roles (rows with unexpected roles)
    invalid_role_count = session.exec(
        select(func.count(Message.id)).where(
            Message.debate_id == debate_id,
            Message.role.notin_(RESPONSE_ROLES),
            Message.role.notin_({"final", "arena_synthesis", "judge", "system", "notice", "user"}),
        )
    ).one()

    # Classification logic (order matters)
    if duplicate_response_count > 0:
        return {
            "classification": "duplicate_responses",
            "response_count": response_count,
            "expected_count": expected_count,
            "duplicate_count": duplicate_response_count,
            "event_count": event_count,
            "total_messages": total_messages,
            "has_final_content": has_final_content,
            "has_synthesis": has_synthesis,
        }

    if invalid_role_count > 0:
        return {
            "classification": "invalid_roles",
            "response_count": response_count,
            "expected_count": expected_count,
            "invalid_role_count": invalid_role_count,
            "event_count": event_count,
            "total_messages": total_messages,
            "has_final_content": has_final_content,
            "has_synthesis": has_synthesis,
        }

    # Check for healthy state
    if response_count > 0 and (expected_count == 0 or response_count >= expected_count):
        return {
            "classification": "healthy",
            "response_count": response_count,
            "expected_count": expected_count,
            "event_count": event_count,
            "total_messages": total_messages,
            "has_final_content": has_final_content,
            "has_synthesis": has_synthesis,
        }

    # Responses missing - check for recoverable data
    if event_count > 0:
        return {
            "classification": "responses_missing_events_recoverable",
            "response_count": response_count,
            "expected_count": expected_count,
            "event_count": event_count,
            "total_messages": total_messages,
            "has_final_content": has_final_content,
            "has_synthesis": has_synthesis,
        }

    if has_final_content:
        return {
            "classification": "responses_missing_final_meta_recoverable",
            "response_count": response_count,
            "expected_count": expected_count,
            "event_count": event_count,
            "total_messages": total_messages,
            "has_final_content": has_final_content,
            "has_synthesis": has_synthesis,
        }

    # Has synthesis but no individual responses and no final_content
    if has_synthesis:
        return {
            "classification": "report_only",
            "response_count": response_count,
            "expected_count": expected_count,
            "event_count": event_count,
            "total_messages": total_messages,
            "has_final_content": has_final_content,
            "has_synthesis": has_synthesis,
        }

    return {
        "classification": "irrecoverable",
        "response_count": response_count,
        "expected_count": expected_count,
        "event_count": event_count,
        "total_messages": total_messages,
        "has_final_content": has_final_content,
        "has_synthesis": has_synthesis,
    }


def recover_from_events(session: Session, debate: Debate, dry_run: bool = True) -> List[Dict[str, Any]]:
    """Recover response data from event rows (non-response roles with content)."""
    events = session.exec(
        select(Message).where(
            Message.debate_id == debate.id,
            Message.role.notin_(RESPONSE_ROLES),
        )
    ).all()

    if not events:
        return []

    # Check for already recovered rows (idempotency)
    existing_recovered = session.exec(
        select(Message).where(
            Message.debate_id == debate.id,
            Message.role.in_(RESPONSE_ROLES),
        )
    ).all()
    
    existing_sources = set()
    for msg in existing_recovered:
        meta = msg.meta or {}
        if meta.get("recovery_source") == "events" and "original_event_id" in meta:
            existing_sources.add(meta["original_event_id"])

    recovered = []
    for event in events:
        meta = event.meta or {}
        # Skip if already recovered
        if str(event.id) in existing_sources:
            continue
            
        if dry_run:
            recovered.append(
                {
                    "id": event.id,
                    "role": event.role,
                    "persona": event.persona,
                    "content_length": len(event.content) if event.content else 0,
                    "recovery_source": "events",
                }
            )
        else:
            # Create a new response message from the event data
            new_message = Message(
                debate_id=debate.id,
                round_index=event.round_index,
                role="arena_response",
                persona=event.persona,
                content=event.content,
                meta={
                    **meta,
                    "recovery_source": "events",
                    "original_event_id": event.id,
                    "recovered_at": _utcnow().isoformat(),
                },
                created_at=event.created_at,
            )
            session.add(new_message)
            recovered.append(
                {
                    "id": event.id,
                    "role": event.role,
                    "persona": event.persona,
                    "content_length": len(event.content) if event.content else 0,
                    "recovery_source": "events",
                }
            )

    return recovered


def recover_from_final_meta(session: Session, debate: Debate, dry_run: bool = True) -> List[Dict[str, Any]]:
    """Recover response data from final_meta/final_content."""
    if not debate.final_content:
        return []

    # Check for idempotency
    existing_recovered = session.exec(
        select(Message).where(
            Message.debate_id == debate.id,
            Message.role.in_(RESPONSE_ROLES),
        )
    ).all()
    
    has_recovered = any(
        (m.meta or {}).get("recovery_source") == "final_meta" 
        for m in existing_recovered
    )
    
    if has_recovered:
        return []

    if dry_run:
        return [
            {
                "source": "final_content",
                "content_length": len(debate.final_content),
                "recovery_source": "final_meta",
            }
        ]

    # Create a new response message from final_content
    new_message = Message(
        debate_id=debate.id,
        round_index=1,
        role="arena_response",
        persona="synthesized",
        content=debate.final_content,
        meta={
            "recovery_source": "final_meta",
            "recovered_at": _utcnow().isoformat(),
        },
        created_at=debate.updated_at or _utcnow(),
    )
    session.add(new_message)

    return [
        {
            "source": "final_content",
            "content_length": len(debate.final_content),
            "recovery_source": "final_meta",
        }
    ]


def record_audit_entry(session: Session, debate_id: str, action: str, details: Dict[str, Any]) -> None:
    """Record an audit log entry."""
    audit_entry = AuditLog(
        action=action,
        target_type="debate",
        target_id=debate_id,
        meta=details,
    )
    session.add(audit_entry)


def audit_debates(
    status: str = "completed",
    created_before: Optional[datetime] = None,
    limit: int = 100,
    debate_id: Optional[str] = None,
    dry_run: bool = True,
    repair: bool = False,
    confirm_debate_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Main audit function."""
    results = {
        "total_debates": 0,
        "classifications": {},
        "recoveries": [],
        "dry_run": dry_run,
        "repair": repair,
        "timestamp": _utcnow().isoformat(),
    }

    with session_scope() as session:
        # Build query
        query = select(Debate).where(Debate.status == status)

        if debate_id:
            query = query.where(Debate.id == debate_id)
        elif created_before:
            query = query.where(Debate.created_at < created_before)

        query = query.order_by(Debate.created_at.desc()).limit(limit)

        debates = session.exec(query).all()
        results["total_debates"] = len(debates)

        for debate in debates:
            classification_result = classify_debate(session, debate)
            classification = classification_result["classification"]

            if classification not in results["classifications"]:
                results["classifications"][classification] = []
            results["classifications"][classification].append(
                {
                    "debate_id": debate.id,
                    "created_at": debate.created_at.isoformat() if debate.created_at else None,
                    "details": classification_result,
                }
            )

            # Perform recovery if requested and not dry_run
            if repair and not dry_run and confirm_debate_id == debate.id:
                if classification == "responses_missing_events_recoverable":
                    recovered = recover_from_events(session, debate, dry_run=False)
                    if recovered:
                        results["recoveries"].append(
                            {
                                "debate_id": debate.id,
                                "method": "events",
                                "recovered_items": len(recovered),
                            }
                        )
                        record_audit_entry(
                            session,
                            debate.id,
                            "historical_response_recovery",
                            {
                                "method": "events",
                                "items_recovered": len(recovered),
                                "dry_run": False,
                            },
                        )

                elif classification == "responses_missing_final_meta_recoverable":
                    recovered = recover_from_final_meta(session, debate, dry_run=False)
                    if recovered:
                        results["recoveries"].append(
                            {
                                "debate_id": debate.id,
                                "method": "final_meta",
                                "recovered_items": len(recovered),
                            }
                        )
                        record_audit_entry(
                            session,
                            debate.id,
                            "historical_response_recovery",
                            {
                                "method": "final_meta",
                                "items_recovered": len(recovered),
                                "dry_run": False,
                            },
                        )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Historical Response Integrity Audit and Safe Repair"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Perform a dry run without making changes (default)",
    )
    parser.add_argument(
        "--status",
        default="completed",
        help="Filter debates by status (default: completed)",
    )
    parser.add_argument(
        "--created-before",
        type=lambda s: datetime.fromisoformat(s),
        help="Filter debates created before this date (ISO format)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of debates to process (default: 100)",
    )
    parser.add_argument(
        "--debate-id",
        help="Specific debate ID to audit",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Enable repair mode (requires --confirm)",
    )
    parser.add_argument(
        "--confirm",
        help="Confirm repair for a specific debate ID",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run audit
    results = audit_debates(
        status=args.status,
        created_before=args.created_before,
        limit=args.limit,
        debate_id=args.debate_id,
        dry_run=args.dry_run,
        repair=args.repair,
        confirm_debate_id=args.confirm,
    )

    # Output results
    print(json.dumps(results, indent=2, default=str))

    # Exit with error if any irrecoverable issues found
    if "irrecoverable" in results["classifications"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
