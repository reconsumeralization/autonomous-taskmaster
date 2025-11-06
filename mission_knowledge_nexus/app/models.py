from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Node(Base):
    __abstract__ = True
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    content = Column(String, nullable=False)
    node_type = Column(String, nullable=False)  # e.g., "mission_intent", "task", "code_file", "documentation"
    extra_metadata = Column(JSON, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = kwargs.get("content", "")
        self.node_type = kwargs.get("node_type", "")
        self.extra_metadata = kwargs.get("extra_metadata", None)

    def dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class MissionIntent(Node):
    __tablename__ = "mission_intents"
    mission_name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    status = Column(String, default="pending")
    tasks = Column(ARRAY(UUID(as_uuid=True)), default=[])


class Task(Node):
    __tablename__ = "tasks"
    mission_intent_id = Column(UUID(as_uuid=True), nullable=False)
    description = Column(String, nullable=False)
    status = Column(String, default="pending")
    assigned_to = Column(String, nullable=True)
    output = Column(String, nullable=True)


class CodeFile(Node):
    __tablename__ = "code_files"
    file_path = Column(String, nullable=False)
    language = Column(String, nullable=False)
    content = Column(String, nullable=False)


class Documentation(Node):
    __tablename__ = "documentation"
    title = Column(String, nullable=False)
    url = Column(String, nullable=True)
    content = Column(String, nullable=False)
