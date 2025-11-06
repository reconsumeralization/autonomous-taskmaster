import asyncio
import httpx
import json
import os
import uuid

NEXUS_API_URL = "http://localhost:8000/graphql"
EXECUTOR_ID = os.environ.get("EXECUTOR_ID", "executor_1")

async def run_executor():
    print(f"Executor {EXECUTOR_ID} starting...")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # 1. Poll for pending tasks
                query = """
                    query GetPendingTasks {
                        semanticSearch(query: "status:pending AND assigned_to:null") {
                            id
                            description
                            node_type
                            ... on TaskGQL {
                                missionIntentId
                            }
                        }
                    }
                """
                response = await client.post(NEXUS_API_URL, json={"query": query})
                response.raise_for_status()
                data = response.json()
                tasks = [t for t in data["data"]["semanticSearch"] if t["node_type"] == "task"]

                if tasks:
                    # For simplicity, just take the first pending task
                    task_to_claim = tasks[0]
                    task_id = task_to_claim["id"]
                    print(f"Executor {EXECUTOR_ID} found pending task: {task_id}")

                    # 2. Claim the task
                    claim_mutation = """
                        mutation ClaimTask($taskId: UUID!, $assignedTo: String!) {
                            claimTask(taskId: $taskId, assignedTo: $assignedTo) {
                                id
                                status
                                assignedTo
                            }
                        }
                    """
                    claim_variables = {"taskId": task_id, "assignedTo": EXECUTOR_ID}
                    claim_response = await client.post(NEXUS_API_URL, json={"query": claim_mutation, "variables": claim_variables})
                    claim_response.raise_for_status()
                    print(f"Executor {EXECUTOR_ID} claimed task {task_id}: {claim_response.json()}")

                    # 3. Simulate work
                    print(f"Executor {EXECUTOR_ID} working on task {task_id}...")
                    await asyncio.sleep(5)  # Simulate work for 5 seconds

                    # 4. Mark task as complete
                    update_mutation = """
                        mutation UpdateTaskStatus($taskId: UUID!, $status: String!, $output: String) {
                            updateTaskStatus(taskId: $taskId, status: $status, output: $output) {
                                id
                                status
                            }
                        }
                    """
                    update_variables = {"taskId": task_id, "status": "completed", "output": f"Task completed by {EXECUTOR_ID}"}
                    update_response = await client.post(NEXUS_API_URL, json={"query": update_mutation, "variables": update_variables})
                    update_response.raise_for_status()
                    print(f"Executor {EXECUTOR_ID} completed task {task_id}: {update_response.json()}")

                else:
                    print(f"Executor {EXECUTOR_ID} no pending tasks. Polling again in 5 seconds...")

            except httpx.RequestError as e:
                print(f"Executor {EXECUTOR_ID} could not connect to Nexus API: {e}")
                print("Please ensure the Nexus API is running at {NEXUS_API_URL}")
            except Exception as e:
                print(f"Executor {EXECUTOR_ID} an unexpected error occurred: {e}")

            await asyncio.sleep(5) # Poll every 5 seconds

if __name__ == "__main__":
    asyncio.run(run_executor())
