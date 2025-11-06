from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional, AsyncGenerator

import strawberry
from fastapi import FastAPI, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

try:
    import nats
except ImportError:
    nats = None  # type: ignore

from mission_knowledge_nexus.app.models import Node, MissionIntent, Task, Base

NATS_URL: str = "nats://localhost:4222"
nc = None  # type: Optional[nats.aio.client.Client] | None

DATABASE_URL: str = (
    "postgresql+asyncpg://nexus_user:nexus_password@localhost:5432/nexus_db"
)
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@strawberry.type
class NodeGQL:
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    content: str
    node_type: str
    extra_metadata: Optional[str]

    @classmethod
    def from_pydantic(cls, instance: Node) -> "NodeGQL":
        return cls(
            id=instance.id,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            content=instance.content,
            node_type=instance.node_type,
            extra_metadata=(
                str(instance.extra_metadata) if instance.extra_metadata else None
            ),
        )


@strawberry.type
class MissionIntentGQL(NodeGQL):
    mission_name: str
    description: str
    status: str
    tasks: List[uuid.UUID]

    @classmethod
    def from_pydantic(cls, instance: MissionIntent) -> "MissionIntentGQL":
        return cls(
            id=instance.id,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            content=instance.content,
            node_type=instance.node_type,
            extra_metadata=(
                str(instance.extra_metadata) if instance.extra_metadata else None
            ),
            mission_name=instance.mission_name,
            description=instance.description,
            status=instance.status,
            tasks=instance.tasks,
        )


@strawberry.type
class TaskGQL(NodeGQL):
    mission_intent_id: uuid.UUID
    description: str
    status: str
    assigned_to: Optional[str]
    output: Optional[str]

    @classmethod
    def from_pydantic(cls, instance: Task) -> "TaskGQL":
        return cls(
            id=instance.id,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
            content=instance.content,
            node_type=instance.node_type,
            extra_metadata=(
                str(instance.extra_metadata) if instance.extra_metadata else None
            ),
            mission_intent_id=instance.mission_intent_id,
            description=instance.description,
            status=instance.status,
            assigned_to=instance.assigned_to,
            output=instance.output,
        )


@strawberry.type
class Query:
    @strawberry.field
    async def getNodeById(
        self, id: uuid.UUID, db: AsyncSession = Depends(get_db)
    ) -> Optional[NodeGQL]:
        result = await db.execute(select(Node).filter(Node.id == id))
        node = result.scalars().first()
        if node:
            return NodeGQL.from_pydantic(node)
        return None

    @strawberry.field
    async def semanticSearch(
        self, query: str, db: AsyncSession = Depends(get_db)
    ) -> List[NodeGQL]:
        result = await db.execute(select(Node).filter(Node.content.ilike(f"%{query}%")))
        nodes = result.scalars().all()
        return [NodeGQL.from_pydantic(node) for node in nodes]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def createMissionIntent(
        self, mission_name: str, description: str, db: AsyncSession = Depends(get_db)
    ) -> MissionIntentGQL:
        new_intent = MissionIntent(
            mission_name=mission_name,
            description=description,
            content=description,
            node_type="mission_intent",
        )
        db.add(new_intent)
        await db.commit()
        await db.refresh(new_intent)
        if nc:
            await nc.publish(
                "intents.new", json.dumps(new_intent.dict(), default=str).encode()
            )
        return MissionIntentGQL.from_pydantic(new_intent)

    @strawberry.mutation
    async def createTask(
        self,
        mission_intent_id: uuid.UUID,
        description: str,
        db: AsyncSession = Depends(get_db),
    ) -> TaskGQL:
        new_task = Task(
            mission_intent_id=mission_intent_id,
            description=description,
            content=description,
            node_type="task",
        )
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        if nc:
            await nc.publish(
                "tasks.new", json.dumps(new_task.dict(), default=str).encode()
            )
        return TaskGQL.from_pydantic(new_task)

    @strawberry.mutation
    async def claimTask(
        self, task_id: uuid.UUID, assigned_to: str, db: AsyncSession = Depends(get_db)
    ) -> TaskGQL:
        task = await db.get(Task, task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found.")
        task.status = "in_progress"
        task.assigned_to = assigned_to
        await db.commit()
        await db.refresh(task)
        if nc:
            await nc.publish(
                "tasks.claimed", json.dumps(task.dict(), default=str).encode()
            )
        return TaskGQL.from_pydantic(task)

    @strawberry.mutation
    async def updateTaskStatus(
        self,
        task_id: uuid.UUID,
        status: str,
        output: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
    ) -> TaskGQL:
        task = await db.get(Task, task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found.")
        task.status = status
        if output:
            task.output = output
        await db.commit()
        await db.refresh(task)
        if nc:
            await nc.publish(
                "tasks.updated", json.dumps(task.dict(), default=str).encode()
            )
        return TaskGQL.from_pydantic(task)


schema = strawberry.Schema(query=Query, mutation=Mutation)

app = FastAPI()


@app.on_event("startup")
async def startup_event() -> None:
    global nc
    if nats is not None:
        nc = await nats.connect(NATS_URL)
        print(f"Connected to NATS at {NATS_URL}")
    else:
        print("NATS client is not installed. Pub/sub will be disabled.")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global nc
    if nc:
        await nc.close()
        print("Disconnected from NATS.")


app.include_router(GraphQLRouter(schema, path="/graphql"))


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Noösphere Nexus API is running!"}
