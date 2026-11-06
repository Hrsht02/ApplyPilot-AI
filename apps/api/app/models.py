import uuid
from datetime import datetime,timezone
from sqlalchemy import String,Text,DateTime,ForeignKey,Integer,JSON,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
class Base(DeclarativeBase): pass
def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__="users"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    google_sub:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    email:Mapped[str]=mapped_column(String(320),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(200))
    picture:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ProviderCredential(Base):
    __tablename__="provider_credentials"
    __table_args__=(UniqueConstraint("user_id","provider",name="uq_user_provider"),)
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    provider:Mapped[str]=mapped_column(String(30))
    encrypted_api_key:Mapped[str]=mapped_column(Text)
    model:Mapped[str]=mapped_column(String(120))
class KnowledgeDocument(Base):
    __tablename__="knowledge_documents"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    filename:Mapped[str]=mapped_column(String(255))
    storage_key:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default="queued")
    extracted_text:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Company(Base):
    __tablename__="companies"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    website_url:Mapped[str]=mapped_column(Text)
    normalized_domain:Mapped[str]=mapped_column(String(255),index=True)
    discovery_status:Mapped[str]=mapped_column(String(30),default="queued")
    discovery_error:Mapped[str|None]=mapped_column(Text,nullable=True)
    last_discovered_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class JobOpening(Base):
    __tablename__="job_openings"
    __table_args__=(UniqueConstraint("company_id","apply_url",name="uq_company_job_url"),)
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    company_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True)
    title:Mapped[str]=mapped_column(String(255))
    description:Mapped[str]=mapped_column(Text)
    apply_url:Mapped[str]=mapped_column(Text)
    match_score:Mapped[int|None]=mapped_column(Integer,nullable=True)
    location:Mapped[str|None]=mapped_column(String(255),nullable=True)
    workplace_type:Mapped[str|None]=mapped_column(String(120),nullable=True)
    source:Mapped[str]=mapped_column(String(40),default="website")
    first_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Application(Base):
    __tablename__="applications"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    job_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("job_openings.id",ondelete="CASCADE"),index=True)
    status:Mapped[str]=mapped_column(String(40),default="discovered")
    answers:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    submitted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
