import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────

class UserStatus(str, enum.Enum):
    STUDENT = "STUDENT"
    ALUMNI = "ALUMNI"


class BadgeRarity(str, enum.Enum):
    COMMON = "COMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"


class MaterialProcessingStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConversationType(str, enum.Enum):
    DIRECT = "DIRECT"
    GROUP = "GROUP"


class ConversationRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class RSVPStatus(str, enum.Enum):
    GOING = "GOING"
    MAYBE = "MAYBE"
    DECLINED = "DECLINED"

# ── University / College / Department / Course ─────────────────────


class DepartmentCatalog(Base):
    __tablename__ = "department_catalog"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class College(Base):
    __tablename__ = "colleges"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, server_default="4")
    university_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("universities.id", ondelete="CASCADE"))

    university: Mapped["University"] = relationship(back_populates="colleges")
    departments: Mapped[list["Department"]] = relationship(back_populates="college", cascade="all, delete-orphan")


class University(Base):
    __tablename__ = "universities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    colleges: Mapped[list["College"]] = relationship(back_populates="university", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="university")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    college_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("colleges.id", ondelete="CASCADE"))

    college: Mapped["College"] = relationship(back_populates="departments")
    courses: Mapped[list["Course"]] = relationship(back_populates="department", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="department")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="department")

    __table_args__ = (Index("ix_departments_college_id", "college_id"),)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    department_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("departments.id", ondelete="SET NULL"))
    is_general: Mapped[bool] = mapped_column(Boolean, default=False)

    department: Mapped["Department | None"] = relationship(back_populates="courses")
    topics: Mapped[list["Topic"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    solved_questions: Mapped[list["SolvedQuestion"]] = relationship(back_populates="course", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_courses_department_id_is_general", "department_id", "is_general"),
        Index("ix_courses_department_id", "department_id"),
    )


# ── User ───────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    matric_number: Mapped[str | None] = mapped_column(String, unique=True)
    entry_year: Mapped[int | None] = mapped_column(Integer)
    current_level: Mapped[str | None] = mapped_column(String)
    level_updated_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    school_email: Mapped[str | None] = mapped_column(String)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="UserStatus", native_enum=False, validate_strings=True),
        default=UserStatus.STUDENT,
    )
    graduated_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    university_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("universities.id", ondelete="RESTRICT"))
    department_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("departments.id", ondelete="RESTRICT"))
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String)
    contribution_score: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[str | None] = mapped_column(String(12), unique=True)
    school_email_prompt_dismissed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    email_prompt_dismissed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    daily_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    daily_tokens_limit: Mapped[int] = mapped_column(Integer, default=50)
    daily_tokens_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())
    last_active_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    user_streak_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("user_streaks.id"))

    university: Mapped["University | None"] = relationship(back_populates="users")
    department: Mapped["Department | None"] = relationship(back_populates="users")
    topics_created: Mapped[list["Topic"]] = relationship("Topic", back_populates="author", foreign_keys="Topic.author_id")
    materials: Mapped[list["Material"]] = relationship(back_populates="uploader")
    lessons_hosted: Mapped[list["Lesson"]] = relationship("Lesson", back_populates="host", foreign_keys="Lesson.host_id")
    rsvps: Mapped[list["RSVP"]] = relationship(back_populates="user")
    emails: Mapped[list["UserEmail"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    privacy: Mapped["UserPrivacy | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    badges: Mapped[list["UserBadge"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversation_memberships: Mapped[list["ConversationMember"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    messages_sent: Mapped[list["Message"]] = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    messages_read: Mapped[list["MessageReadReceipt"]] = relationship(back_populates="user")
    conversations_created: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="created_by", foreign_keys="Conversation.created_by_id")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    streak: Mapped["UserStreak | None"] = relationship(back_populates="users", uselist=False)
    points_transactions: Mapped[list["PointsTransaction"]] = relationship(back_populates="user")
    reward_purchases: Mapped[list["UserRewardPurchase"]] = relationship(back_populates="user")
    material_unlocks: Mapped[list["MaterialUnlock"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
        foreign_keys="MaterialUnlock.user_id",
    )
    questions_asked: Mapped[list["TopicQuestion"]] = relationship("TopicQuestion", back_populates="author", foreign_keys="TopicQuestion.author_id")
    answers_provided: Mapped[list["QuestionAnswer"]] = relationship("QuestionAnswer", back_populates="author", foreign_keys="QuestionAnswer.author_id")
    referrals_made: Mapped[list["Referral"]] = relationship("Referral", back_populates="referrer", foreign_keys="Referral.referrer_id")
    referral_received: Mapped["Referral | None"] = relationship("Referral", back_populates="referee", foreign_keys="Referral.referee_id")

    __table_args__ = (
        Index("ix_users_department_id", "department_id"),
        Index("ix_users_university_id", "university_id"),
        Index("ix_users_current_level", "current_level"),
        Index("ix_users_status", "status"),
    )


class UserPrivacy(Base):
    __tablename__ = "user_privacy"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    is_stealth_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    show_contributions: Mapped[bool] = mapped_column(Boolean, default=True)
    show_email: Mapped[bool] = mapped_column(Boolean, default=False)
    show_department: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="privacy")

    __table_args__ = (Index("ix_user_privacy_user_id", "user_id"),)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    bio: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String)
    social_links: Mapped[dict | None] = mapped_column(JSON)
    profile_image_url: Mapped[str | None] = mapped_column(String)
    banner_image_url: Mapped[str | None] = mapped_column(String)
    last_profile_view: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")

    __table_args__ = (Index("ix_user_profiles_user_id", "user_id"),)


class UserEmail(Base):
    __tablename__ = "user_emails"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="emails")

    __table_args__ = (
        Index("ix_user_emails_user_id", "user_id"),
        Index("ix_user_emails_email", "email"),
    )


# ── Badge ──────────────────────────────────────────────────────────

class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String, nullable=False)
    rarity: Mapped[BadgeRarity] = mapped_column(
        Enum(BadgeRarity, name="BadgeRarity", native_enum=False, validate_strings=True),
        default=BadgeRarity.COMMON,
    )
    criteria: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    users: Mapped[list["UserBadge"]] = relationship(back_populates="badge", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_badges_rarity", "rarity"),)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    badge_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("badges.id", ondelete="CASCADE"))
    earned_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    awarded_by: Mapped[str | None] = mapped_column(String)

    user: Mapped["User"] = relationship(back_populates="badges")
    badge: Mapped["Badge"] = relationship(back_populates="users")

    __table_args__ = (
        Index("ix_user_badges_user_id", "user_id"),
        Index("ix_user_badges_badge_id", "badge_id"),
    )


# ── Topic / Material ───────────────────────────────────────────────

class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    course_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"))
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_activity: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    course: Mapped["Course"] = relationship(back_populates="topics")
    author: Mapped["User"] = relationship("User", back_populates="topics_created", foreign_keys=[author_id])
    materials: Mapped[list["Material"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="topic")
    questions: Mapped[list["TopicQuestion"]] = relationship(back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_topics_course_id", "course_id"),
        Index("ix_topics_last_activity", "last_activity"),
        Index("ix_topics_course_id_is_active_last_activity", "course_id", "is_active", "last_activity"),
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_url: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="CASCADE"))
    uploader_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    processing_status: Mapped[MaterialProcessingStatus] = mapped_column(
        Enum(MaterialProcessingStatus, name="MaterialProcessingStatus", native_enum=False, validate_strings=True),
        default=MaterialProcessingStatus.QUEUED,
    )
    processing_job_id: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    questions: Mapped[dict | None] = mapped_column(JSON)
    tips: Mapped[dict | None] = mapped_column(JSON)
    processing_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=True)
    is_past_question: Mapped[bool] = mapped_column(Boolean, default=False)
    exam_year: Mapped[int | None] = mapped_column(Integer)
    semester: Mapped[str | None] = mapped_column(String)
    content_hash: Mapped[str | None] = mapped_column(String(64))

    topic: Mapped["Topic"] = relationship(back_populates="materials")
    uploader: Mapped["User"] = relationship(back_populates="materials")
    unlocks: Mapped[list["MaterialUnlock"]] = relationship(back_populates="material", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_materials_processing_status", "processing_status"),
        Index("ix_materials_processing_job_id", "processing_job_id"),
        Index("ix_materials_uploaded_at", "uploaded_at"),
        Index("ix_materials_topic_id_uploaded_at", "topic_id", "uploaded_at"),
        Index("ix_materials_topic_id_is_seed", "topic_id", "is_seed"),
        Index("ix_materials_is_seed", "is_seed"),
        Index("ix_materials_content_hash", "content_hash"),
    )


class MaterialUnlock(Base):
    __tablename__ = "material_unlocks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    material_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("materials.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    referrer_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="unlocks")
    user: Mapped["User"] = relationship(back_populates="material_unlocks", foreign_keys=[user_id])
    referrer: Mapped["User | None"] = relationship("User", foreign_keys=[referrer_id])

    __table_args__ = (
        UniqueConstraint("user_id", "material_id", name="uq_material_unlocks_user_material"),
        Index("ix_material_unlocks_material_id", "material_id"),
        Index("ix_material_unlocks_user_id", "user_id"),
        Index("ix_material_unlocks_referrer_id", "referrer_id"),
    )


# ── Collaboration ──────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    type: Mapped[ConversationType] = mapped_column(
        Enum(ConversationType, name="ConversationType", native_enum=False, validate_strings=True),
        default=ConversationType.GROUP,
    )
    title: Mapped[str | None] = mapped_column(String)
    department_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("departments.id", ondelete="SET NULL"))
    topic_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="SET NULL"))
    created_by_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    department: Mapped["Department | None"] = relationship(back_populates="conversations")
    topic: Mapped["Topic | None"] = relationship(back_populates="conversations")
    created_by: Mapped["User"] = relationship("User", back_populates="conversations_created", foreign_keys=[created_by_id])
    members: Mapped[list["ConversationMember"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_conversations_department_id", "department_id"),
        Index("ix_conversations_topic_id", "topic_id"),
        Index("ix_conversations_created_by_id", "created_by_id"),
        Index("ix_conversations_updated_at", "updated_at"),
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[ConversationRole] = mapped_column(
        Enum(ConversationRole, name="ConversationRole", native_enum=False, validate_strings=True),
        default=ConversationRole.MEMBER,
    )
    last_read_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="conversation_memberships")

    __table_args__ = (
        Index("ix_conversation_members_user_id", "user_id"),
        Index("ix_conversation_members_conversation_id", "conversation_id"),
        Index("ix_conversation_members_last_read_at", "last_read_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON)
    edited_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship("User", back_populates="messages_sent", foreign_keys=[sender_id])
    receipts: Mapped[list["MessageReadReceipt"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="source_message")

    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
        Index("ix_messages_sender_id", "sender_id"),
        Index("ix_messages_deleted_at", "deleted_at"),
        Index("ix_messages_conversation_id_deleted_at_created_at", "conversation_id", "deleted_at", "created_at"),
    )


class MessageReadReceipt(Base):
    __tablename__ = "message_read_receipts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    message_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("messages.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    read_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="receipts")
    user: Mapped["User"] = relationship(back_populates="messages_read")

    __table_args__ = (
        Index("ix_message_read_receipts_user_id", "user_id"),
        Index("ix_message_read_receipts_message_id", "message_id"),
        Index("ix_message_read_receipts_read_at", "read_at"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    source_message_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("messages.id", ondelete="SET NULL"))
    delivered_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    read_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="notifications")
    source_message: Mapped["Message | None"] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_kind", "kind"),
        Index("ix_notifications_read_at", "read_at"),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
    )


# ── Gamification ───────────────────────────────────────────────────

class UserStreak(Base):
    __tablename__ = "user_streaks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    streak_started_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="streak")

    __table_args__ = (
        Index("ix_user_streaks_user_id", "user_id"),
        Index("ix_user_streaks_current_streak", "current_streak"),
    )


class PointsTransaction(Base):
    __tablename__ = "points_transactions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    related_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="points_transactions")

    __table_args__ = (
        Index("ix_points_transactions_user_id", "user_id"),
        Index("ix_points_transactions_created_at", "created_at"),
        Index("ix_points_transactions_user_id_created_at", "user_id", "created_at"),
    )


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    referrer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    referee_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    referrer: Mapped["User"] = relationship("User", back_populates="referrals_made", foreign_keys=[referrer_id])
    referee: Mapped["User"] = relationship("User", back_populates="referral_received", foreign_keys=[referee_id])

    __table_args__ = (
        UniqueConstraint("referee_id", name="uq_referrals_referee"),
        Index("ix_referrals_referrer_id", "referrer_id"),
        Index("ix_referrals_referee_id", "referee_id"),
    )


class RewardItem(Base):
    __tablename__ = "reward_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    __table_args__ = (
        Index("ix_reward_items_is_active", "is_active"),
        Index("ix_reward_items_points_cost", "points_cost"),
    )


class UserRewardPurchase(Base):
    __tablename__ = "user_reward_purchases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    reward_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    redeemed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="reward_purchases")

    __table_args__ = (
        Index("ix_user_reward_purchases_user_id", "user_id"),
        Index("ix_user_reward_purchases_reward_id", "reward_id"),
        Index("ix_user_reward_purchases_redeemed_at", "redeemed_at"),
    )


# ── Q&A ────────────────────────────────────────────────────────────

class TopicQuestion(Base):
    __tablename__ = "topic_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    topic_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="CASCADE"))
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    help_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    topic: Mapped["Topic"] = relationship(back_populates="questions")
    author: Mapped["User"] = relationship("User", back_populates="questions_asked", foreign_keys=[author_id])
    answers: Mapped[list["QuestionAnswer"]] = relationship(back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_topic_questions_topic_id", "topic_id"),
        Index("ix_topic_questions_created_at", "created_at"),
        Index("ix_topic_questions_is_resolved", "is_resolved"),
        Index("ix_topic_questions_help_count", "help_count"),
    )


class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    question_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("topic_questions.id", ondelete="CASCADE"))
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    help_count: Mapped[int] = mapped_column(Integer, default=0)
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    question: Mapped["TopicQuestion"] = relationship(back_populates="answers")
    author: Mapped["User"] = relationship("User", back_populates="answers_provided", foreign_keys=[author_id])

    __table_args__ = (
        Index("ix_question_answers_question_id", "question_id"),
        Index("ix_question_answers_help_count", "help_count"),
        Index("ix_question_answers_is_accepted", "is_accepted"),
    )


# ── Vault / Lesson / RSVP ─────────────────────────────────────────

class VaultItem(Base):
    __tablename__ = "vault_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    local_blob_id: Mapped[str] = mapped_column(String, nullable=False)
    saved_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    user: Mapped["User"] = relationship(backref="vault_items")

    __table_args__ = (Index("ix_vault_items_user_id", "user_id"),)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    host_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"))
    course_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    host: Mapped["User"] = relationship("User", back_populates="lessons_hosted", foreign_keys=[host_id])
    course: Mapped["Course"] = relationship(back_populates="lessons")
    rsvps: Mapped[list["RSVP"]] = relationship(back_populates="lesson", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_lessons_course_id_scheduled_for", "course_id", "scheduled_for"),)


class RSVP(Base):
    __tablename__ = "rsvps"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("lessons.id", ondelete="CASCADE"))
    status: Mapped[RSVPStatus] = mapped_column(
        Enum(RSVPStatus, name="RSVPStatus", native_enum=False, validate_strings=True),
        default=RSVPStatus.GOING,
    )
    responded_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="rsvps")
    lesson: Mapped["Lesson"] = relationship(back_populates="rsvps")

    __table_args__ = ()


# ── Connected Accounts (Google Drive) ─────────────────────────────

class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String, nullable=False)  # "google"
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(backref="connected_accounts")

    __table_args__ = (
        Index("ix_connected_accounts_user_id", "user_id"),
        Index("ix_connected_accounts_provider", "provider"),
    )


# ── Imported Files (from Google Drive) ────────────────────────────

class ImportedFile(Base):
    __tablename__ = "imported_files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    drive_file_id: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    folder_path: Mapped[str | None] = mapped_column(String)
    material_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("materials.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, importing, imported, failed
    error: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    user: Mapped["User"] = relationship(backref="imported_files")

    __table_args__ = (
        Index("ix_imported_files_user_id", "user_id"),
        Index("ix_imported_files_drive_file_id", "drive_file_id"),
        Index("ix_imported_files_status", "status"),
    )


# ── Flashcards ─────────────────────────────────────────────────────

class FlashcardDeck(Base):
    __tablename__ = "flashcard_decks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(String)
    course_code: Mapped[str | None] = mapped_column(String)
    card_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(backref="flashcard_decks")
    cards: Mapped[list["Flashcard"]] = relationship(back_populates="deck", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_flashcard_decks_user_id", "user_id"),
    )


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    deck_id: Mapped[str] = mapped_column(String, ForeignKey("flashcard_decks.id", ondelete="CASCADE"))
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    ease_factor: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    deck: Mapped["FlashcardDeck"] = relationship(back_populates="cards")

    __table_args__ = (
        Index("ix_flashcards_deck_id", "deck_id"),
        Index("ix_flashcards_next_review", "next_review"),
    )


# ── Subscriptions (Paystack Premium) ──────────────────────────────

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    reference: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    quota_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    storage_bytes_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_bytes_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(backref="subscriptions")

    __table_args__ = (
        Index("ix_subscriptions_user_id", "user_id"),
        Index("ix_subscriptions_reference", "reference"),
        Index("ix_subscriptions_status", "status"),
    )


# ── Solved Question Bank ────────────────────────────────────────────

class SolvedQuestionStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SolvedBankBatch(Base):
    """A batch generation run of the Solved Question Bank for one course.

    Tracks queued/completed/failed counts and cumulative USD cost so the
    per-question margin (the core ROI story) is auditable.
    """

    __tablename__ = "solved_bank_batches"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    course_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"))
    trigger: Mapped[str] = mapped_column(String, default="manual")  # manual | schedule
    target_count: Mapped[int] = mapped_column(Integer, default=300)
    queued_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd_total: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String, default="RUNNING")  # RUNNING | COMPLETED | FAILED
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    course: Mapped["Course"] = relationship()
    questions: Mapped[list["SolvedQuestion"]] = relationship(back_populates="batch", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_solved_bank_batches_course_id", "course_id"),
        Index("ix_solved_bank_batches_status", "status"),
    )


class SolvedQuestion(Base):
    """A single past exam question with a cached AI answer.

    ``question_hash`` is a content fingerprint used for deduplication, so the
    same question asked in different papers (or schools) is solved exactly once.
    """

    __tablename__ = "solved_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    batch_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("solved_bank_batches.id", ondelete="SET NULL"))
    course_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"))
    material_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("materials.id", ondelete="SET NULL"))
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    semester: Mapped[str | None] = mapped_column(String)
    model: Mapped[str] = mapped_column(String, default="gemini-flash-lite-latest")
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[SolvedQuestionStatus] = mapped_column(
        Enum(SolvedQuestionStatus, name="SolvedQuestionStatus", native_enum=False, validate_strings=True),
        default=SolvedQuestionStatus.QUEUED,
    )
    error: Mapped[str | None] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    generated_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), onupdate=func.now())

    batch: Mapped["SolvedBankBatch | None"] = relationship(back_populates="questions")
    course: Mapped["Course"] = relationship(back_populates="solved_questions")
    material: Mapped["Material | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("question_hash", name="uq_solved_questions_hash"),
        Index("ix_solved_questions_course_id", "course_id"),
        Index("ix_solved_questions_course_id_status", "course_id", "status"),
        Index("ix_solved_questions_course_id_is_sample", "course_id", "is_sample"),
    )
