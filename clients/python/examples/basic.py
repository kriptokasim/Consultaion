"""Example usage of the Consultaion Python SDK."""

import asyncio
import os

from consultaion import ConsultaionClient


async def main() -> None:
    """Main example function."""
    # Initialize the client with your API endpoint
    api_url = os.getenv("CONSULTAION_API_URL", "http://localhost:8000")
    api_key = os.getenv("CONSULTAION_API_KEY")

    async with ConsultaionClient(base_url=api_url, api_key=api_key) as client:
        try:
            print("Creating a debate with smart routing...\n")

            # Create a debate
            debate = await client.create_debate(
                {
                    "prompt": "What are the ethical implications of AI in healthcare?",
                    "routing_policy": "router-smart",
                }
            )

            print(f"✅ Debate created: {debate['id']}")
            print(f"📊 Routed model: {debate.get('routed_model', 'N/A')}")

            if debate.get("routing_meta") and debate["routing_meta"].get("candidates"):
                print("\n🎯 Top routing candidates:")
                for i, candidate in enumerate(debate["routing_meta"]["candidates"][:3], 1):
                    score = candidate["total_score"]
                    print(f"  {i}. {candidate['model']} (score: {score:.3f})")

            print(f"\n⏳ Status: {debate['status']}")

            # Stream events
            print("\n📡 Streaming events...\n")

            event_count = 0
            async for event in client.stream_events(debate["id"]):
                event_count += 1
                print(f"[{event['type']}] {event['data']}")

                # Stop after 10 events for demo purposes
                if event_count >= 10:
                    print("\n🛑 Stopping stream (demo limit reached)...")
                    break

        except Exception as e:
            print(f"❌ Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
