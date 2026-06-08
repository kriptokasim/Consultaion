import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from uuid import uuid4
from agents import _call_llm, USE_MOCK

logger = logging.getLogger(__name__)

async def generate_reasoning_chain(
    prompt: str,
    preceding_nodes: Optional[List[Dict[str, Any]]] = None,
    fork_assumption: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generates a step-by-step reasoning chain of thought.
    If preceding_nodes and fork_assumption are provided, it forks the reasoning
    by appending the fork assumption and continuing the logic.
    """
    if USE_MOCK:
        await asyncio.sleep(0.5)
        if preceding_nodes and fork_assumption:
            # Fork mode
            base_nodes = list(preceding_nodes)
            fork_node_id = f"node_{str(uuid4())[:8]}"
            base_nodes.append({
                "id": fork_node_id,
                "title": "Fork Assumption",
                "type": "claim",
                "content": f"Fork: {fork_assumption}"
            })
            base_nodes.append({
                "id": f"node_{str(uuid4())[:8]}",
                "title": "Evaluate assumption impact",
                "type": "uncertainty",
                "content": "Analyzing how this new parameter changes the logical constraints of the system."
            })
            base_nodes.append({
                "id": f"node_{str(uuid4())[:8]}",
                "title": "Revised Conclusion",
                "type": "conclusion",
                "content": f"Under the assumption that '{fork_assumption}', we recommend configuring localized caches with TLS encryption."
            })
            return base_nodes
        else:
            # Base mode
            return [
                {
                    "id": f"node_{str(uuid4())[:8]}",
                    "title": "Premise Analysis",
                    "type": "fact",
                    "content": f"The query parameter is evaluated: '{prompt}'."
                },
                {
                    "id": f"node_{str(uuid4())[:8]}",
                    "title": "Vulnerability Check",
                    "type": "uncertainty",
                    "content": "A potential single point of failure exists in the unauthenticated database schema."
                },
                {
                    "id": f"node_{str(uuid4())[:8]}",
                    "title": "Remediation Strategy",
                    "type": "claim",
                    "content": "Implementing a stateless JWT authentication layer will mitigate unauthorized queries."
                },
                {
                    "id": f"node_{str(uuid4())[:8]}",
                    "title": "System Recommendation",
                    "type": "conclusion",
                    "content": "Use a secure proxy wrapper and enforce HTTPS to prevent sniffing."
                }
            ]

    # Real LLM execution
    if preceding_nodes and fork_assumption:
        # Fork logic
        preceding_str = json.dumps(preceding_nodes, indent=2)
        system_msg = (
            "You are an AI Oracle reasoning engine that outputs structured step-by-step logical chains of thought. "
            "Each step is a node with keys: 'id', 'title', 'content', and 'type' ('fact' | 'claim' | 'uncertainty' | 'conclusion'). "
            "Output strictly a valid JSON array of node objects representing the new continuation steps."
        )
        user_msg = (
            f"Preceding reasoning nodes:\n{preceding_str}\n\n"
            f"The user has introduced a new counter-assumption or fork condition:\n"
            f"'{fork_assumption}'\n\n"
            f"Identify the logical consequences of this fork. Generate 2 to 4 remaining reasoning nodes "
            f"starting with a node evaluating this counter-assumption, and concluding with a new 'conclusion' node. "
            f"Provide unique 'id' values for the new nodes. Output raw JSON only."
        )
    else:
        # Base logic
        system_msg = (
            "You are an AI Oracle reasoning engine that outputs structured step-by-step logical chains of thought. "
            "Each step is a node with keys: 'id', 'title', 'content', and 'type' ('fact' | 'claim' | 'uncertainty' | 'conclusion'). "
            "Output strictly a valid JSON array of node objects (4-5 steps total)."
        )
        user_msg = (
            f"Query: '{prompt}'\n\n"
            f"Provide a step-by-step logical chain of thought to solve/analyze the query. "
            f"Classify the nodes appropriately ('fact', 'claim', 'uncertainty', 'conclusion'). Output raw JSON only."
        )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]

    try:
        text, _ = await _call_llm(
            messages,
            role="Oracle_Reasoning",
            temperature=0.2,
            max_tokens=1000
        )

        clean_text = text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        new_nodes = json.loads(clean_text)
        if not isinstance(new_nodes, list):
            new_nodes = []

        # Validate structure of each node
        for node in new_nodes:
            if "id" not in node:
                node["id"] = f"node_{str(uuid4())[:8]}"
            if "title" not in node:
                node["title"] = "Reasoning step"
            if "content" not in node:
                node["content"] = ""
            if node.get("type") not in ["fact", "claim", "uncertainty", "conclusion"]:
                node["type"] = "claim"

        if preceding_nodes and fork_assumption:
            # Reconstruct the combined list
            fork_node_id = f"node_{str(uuid4())[:8]}"
            combined = list(preceding_nodes)
            combined.append({
                "id": fork_node_id,
                "title": "Fork Assumption",
                "type": "claim",
                "content": fork_assumption
            })
            combined.extend(new_nodes)
            return combined
        else:
            return new_nodes
    except Exception as exc:
        logger.error(f"Oracle reasoning generation failed: {exc}")
        # Return fallback
        fallback = [{
            "id": f"node_{str(uuid4())[:8]}",
            "title": "Reasoning Error",
            "type": "uncertainty",
            "content": f"Failed to complete the logical chain: {exc}"
        }]
        if preceding_nodes:
            return preceding_nodes + fallback
        return fallback
