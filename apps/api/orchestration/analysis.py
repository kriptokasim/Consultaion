import json
import logging
import re
from typing import Any, Dict, List

from agents import call_llm_for_role
from database_async import async_session_scope
from models import Debate, DebateTurn
from sqlmodel import select

logger = logging.getLogger(__name__)

async def extract_debate_turn_analysis(debate_id: str, round_index: int, messages: List[Dict[str, Any]]) -> None:
    """
    Extracts key arguments and position drift coordinates for each model's message in a round,
    persisting them to the database as DebateTurn records.
    """
    try:
        # 1. Fetch debate prompt and active moderation steering (if any)
        async with async_session_scope() as session:
            debate = await session.get(Debate, debate_id)
            if not debate:
                logger.warning(f"Debate {debate_id} not found for turn analysis.")
                return
            prompt = debate.prompt

            # Check if there is already a moderation steering record for this round
            stmt = select(DebateTurn).where(
                DebateTurn.debate_id == debate_id,
                DebateTurn.round_index == round_index
            )
            res = await session.execute(stmt)
            existing_turns = res.scalars().all()
            
            # Extract steering if it exists
            moderation_steering = None
            for turn in existing_turns:
                if turn.moderation_steering:
                    moderation_steering = turn.moderation_steering
                    break

        # 2. Extract arguments & stance for each message
        for msg in messages:
            agent_id = msg.get("persona")
            content = msg.get("text", "")
            if not agent_id or not content:
                continue

            # Check if we already have an analyzed turn for this agent
            already_done = False
            for turn in existing_turns:
                if turn.agent_id == agent_id and turn.claims_nodes is not None:
                    already_done = True
                    break
            if already_done:
                continue

            # LLM prompt to extract structured arguments and drift
            system_prompt = (
                "You are a debate analyst. Analyze the given debater's response relative to the starting debate prompt/topic. \n"
                "Your task is to extract:\n"
                "1. Logical argument claims (claims_nodes): An array of 2-4 key points made. Each node has:\n"
                "   - id: a short alphanumeric string (e.g. 'c1', 'c2')\n"
                "   - type: 'pro' (supporting the prompt), 'contra' (opposing/critiquing the prompt), or 'rebuttal' (countering other views)\n"
                "   - claim: a concise claim under 15 words\n"
                "   - rebuts_target: if type is 'rebuttal', specify the node ID it targets or null\n"
                "2. Position Drift (position_drift): Stance coordinates relative to the prompt (values from 0.0 to 1.0):\n"
                "   - stubbornness: 0.0 (very flexible/adaptive) to 1.0 (unyielding, refusing to modify stance)\n"
                "   - cooperativeness: 0.0 (combative, purely oppositional) to 1.0 (highly collaborative, building consensus)\n"
                "   - explanation: a brief 1-sentence explanation of why these coordinates were assigned.\n\n"
                "Output strictly as a single JSON object matching this structure:\n"
                "{\n"
                '  "claims_nodes": [\n'
                '     {"id": "c1", "type": "pro", "claim": "Text here", "rebuts_target": null}\n'
                "  ],\n"
                '  "position_drift": {\n'
                '     "stubbornness": 0.5,\n'
                '     "cooperativeness": 0.7,\n'
                '     "explanation": "Stated economic tradeoffs while acknowledging peer points."\n'
                "  }\n"
                "}"
            )

            user_content = f"Starting Debate Topic: {prompt}\n\nAgent Response:\n{content}"
            messages_payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            claims_nodes = []
            position_drift = {
                "stubbornness": 0.5,
                "cooperativeness": 0.5,
                "explanation": "Standard starting stance."
            }

            try:
                raw, _ = await call_llm_for_role(
                    messages_payload,
                    role="Debate:TurnAnalyzer",
                    temperature=0.1,
                    max_tokens=400,
                    debate_id=debate_id
                )
                match = re.search(r"\{.*\}", raw, flags=re.S)
                if match:
                    data = json.loads(match.group(0))
                    claims_nodes = data.get("claims_nodes", [])
                    position_drift = data.get("position_drift", position_drift)
            except Exception as e:
                logger.warning(f"Failed to analyze turn for debate {debate_id}, agent {agent_id}: {e}")

            # 3. Persist DebateTurn record
            async with async_session_scope() as session:
                # See if we have an existing empty placeholder to update, or create a new one
                stmt = select(DebateTurn).where(
                    DebateTurn.debate_id == debate_id,
                    DebateTurn.round_index == round_index,
                    DebateTurn.agent_id == agent_id
                )
                res = await session.execute(stmt)
                turn_rec = res.scalar_one_or_none()

                if turn_rec:
                    turn_rec.claims_nodes = claims_nodes
                    turn_rec.position_drift = position_drift
                    if moderation_steering:
                        turn_rec.moderation_steering = moderation_steering
                    session.add(turn_rec)
                else:
                    turn_rec = DebateTurn(
                        debate_id=debate_id,
                        round_index=round_index,
                        agent_id=agent_id,
                        claims_nodes=claims_nodes,
                        position_drift=position_drift,
                        moderation_steering=moderation_steering
                    )
                    session.add(turn_rec)
                await session.commit()

    except Exception as exc:
        logger.error(f"Error executing turn analysis for debate {debate_id}: {exc}")
