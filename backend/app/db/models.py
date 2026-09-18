import datetime
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    recruitment_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, running, ambiguous, completed, failed
    current_step = Column(String, default="initialized")
    candidates_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class RecruitmentModel(Base):
    __tablename__ = "recruitments"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    org = Column(String, nullable=False)
    year = Column(String, nullable=False)
    advt_number = Column(String, nullable=False)
    post = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SourceModel(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True)
    recruitment_id = Column(String, ForeignKey("recruitments.id"), nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class FactModel(Base):
    __tablename__ = "facts"

    id = Column(String, primary_key=True)
    recruitment_id = Column(String, ForeignKey("recruitments.id"), nullable=False)
    field = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source_date = Column(String, nullable=True)
    confidence = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ConflictModel(Base):
    __tablename__ = "conflicts"

    id = Column(String, primary_key=True)
    recruitment_id = Column(String, ForeignKey("recruitments.id"), nullable=False)
    field = Column(String, nullable=False)
    conflicting_facts_json = Column(Text, nullable=False)
    resolved_value = Column(Text, nullable=True)
    resolution_reason = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserRequestModel(Base):
    __tablename__ = "user_requests"

    id = Column(String, primary_key=True)
    recruitment_id = Column(String, ForeignKey("recruitments.id"), nullable=False)
    request_text = Column(Text, nullable=False)
    affected_sections_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    recruitment_id = Column(String, ForeignKey("recruitments.id"), nullable=False)
    version = Column(String, nullable=False, default="1.0")
    changed_sections_json = Column(Text, nullable=False, default="[]")
    source_request_id = Column(String, ForeignKey("user_requests.id"), nullable=True)
    sections_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
