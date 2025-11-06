import asyncio
import nats
import json
import httpx
import os

NATS_URL = "nats://localhost:4222"
NEXUS_API_URL = "http://localhost:8000/graphql"

async def run_prime_conductor():
    nc = None
    try:
        nc = await nats.connect(NATS_URL)
        print(f"Prime Conductor connected to NATS at {NATS_URL}")

        async def message_handler(msg):
            subject = msg.subject
            data = json.loads(msg.data.decode())
            print(f"Received on '{subject}': {data}")

            if subject == "intents.new":
                intent_id = data["id"]
                print(f"New Intent detected: {intent_id}. Decomposing...")

                # Simulate decomposition and task creation
                async with httpx.AsyncClient() as client:
                    # Create dummy task 1
                    task1_description = "Analyze market trends for new product"
                    task1_query = """
                        mutation CreateTask($missionIntentId: UUID!, $description: String!) {
                            createTask(missionIntentId: $missionIntentId, description: $description) {
                                id
                                description
                                status
                            }
                        }
                    """
                    task1_variables = {"missionIntentId": intent_id, "description": task1_description}
                    response = await client.post(NEXUS_API_URL, json={"query": task1_query, "variables": task1_variables})
                    response.raise_for_status()
                    print(f"Created dummy task 1: {response.json()}")

                    # Create dummy task 2
                    task2_description = "Draft initial security constraints"
                    task2_query = """
                        mutation CreateTask($missionIntentId: UUID!, $description: String!) {
                            createTask(missionIntentId: $missionIntentId, description: $description) {
                                id
                                description
                                status
                            }
                        }
                    """
                    task2_variables = {"missionIntentId": intent_id, "description": task2_description}
                    response = await client.post(NEXUS_API_URL, json={"query": task2_query, "variables": task2_variables})
                    response.raise_for_status()
                    print(f"Created dummy task 2: {response.json()}")

        await nc.subscribe("intents.new", cb=message_handler)
        print("Prime Conductor is listening for new intents...")

        while True:
            await asyncio.sleep(1) # Keep the conductor running

    except nats.errors.NoServersError as e:
        print(f"Could not connect to NATS: {e}")
        print("Please ensure a NATS server is running at {NATS_URL}")
    except httpx.RequestError as e:
        print(f"Could not connect to Nexus API: {e}")
        print("Please ensure the Nexus API is running at {NEXUS_API_URL}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if nc:
            await nc.close()

if __name__ == "__main__":
    asyncio.run(run_prime_conductor())
