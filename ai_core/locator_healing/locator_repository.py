"""
Locator Repository — SQLite-Backed Cache for Healed Locator Mappings

Persists the mapping from original (broken) locators to their healed
replacements, including confidence scores, LLM reasoning, test context,
and timestamps. This serves two critical purposes:

1. **Caching**: Future test runs check the repository before calling the
   LLM, avoiding redundant API calls for previously healed locators.

2. **Audit Trail**: Every healing attempt (successful or not) is recorded
   for compliance, debugging, and the healing report dashboard.

Uses SQLAlchemy with SQLite for zero-configuration setup. The database
is created automatically at data/healing_history.db.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text,
    Boolean, Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger(__name__)

Base = declarative_base()

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


class HealingRecord(Base):
    """
    SQLAlchemy model for a locator healing record.

    Stores the complete context of each healing attempt for caching,
    auditing, and report generation.
    """
    __tablename__ = "healing_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Original (broken) locator
    original_selector = Column(String(500), nullable=False, index=True)
    original_strategy = Column(String(50), nullable=False, default="css")

    # Healed (replacement) locator
    healed_selector = Column(String(500), nullable=True)
    healed_strategy = Column(String(50), nullable=True)

    # Confidence and reasoning
    confidence = Column(Float, nullable=False, default=0.0)
    reasoning = Column(Text, nullable=True)
    decision = Column(String(50), nullable=False)  # auto_heal, suggest, reject

    # Test context
    test_name = Column(String(300), nullable=True)
    page_url = Column(String(1000), nullable=True)
    element_intent = Column(String(500), nullable=True)

    # LLM metadata
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    llm_latency_ms = Column(Float, nullable=True)

    # Status
    status = Column(String(50), nullable=False, default="healed")
    is_cached_hit = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Composite index for cache lookups
    __table_args__ = (
        Index("idx_cache_lookup", "original_selector", "original_strategy", "page_url"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "original_selector": self.original_selector,
            "original_strategy": self.original_strategy,
            "healed_selector": self.healed_selector,
            "healed_strategy": self.healed_strategy,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "decision": self.decision,
            "test_name": self.test_name,
            "page_url": self.page_url,
            "element_intent": self.element_intent,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_latency_ms": self.llm_latency_ms,
            "status": self.status,
            "is_cached_hit": self.is_cached_hit,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LocatorRepository:
    """
    SQLite-backed repository for healed locator storage and retrieval.

    Provides:
    - Cache lookup: Check if a broken locator has been healed before
    - Save: Persist new healing results
    - Audit log: Query healing history for reporting
    - TTL management: Cached healings expire after configurable period

    Usage:
        repo = LocatorRepository()
        
        # Check cache before calling LLM
        cached = repo.lookup("#old-login-btn", strategy="css")
        if cached:
            use_healed_locator(cached)
        
        # Save a new healing result
        repo.save(healing_result)
        
        # Generate audit report
        recent = repo.get_recent_healings(hours=24)
    """

    def __init__(self, db_path: Optional[str] = None, cache_ttl_hours: int = 168):
        """
        Initialize the locator repository.

        Args:
            db_path: Path to the SQLite database. Defaults to config value.
            cache_ttl_hours: How long cached healings are valid (default: 168 = 7 days).
        """
        if db_path is None:
            db_path = self._get_db_path()

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.cache_ttl_hours = cache_ttl_hours
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

        logger.info(
            "LocatorRepository initialized: db=%s, cache_ttl=%dh",
            db_path, cache_ttl_hours,
        )

    @staticmethod
    def _get_db_path() -> str:
        """Load the database path from config.yaml."""
        try:
            import yaml
            with open(_CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            healing_config = config.get("healing", {}).get("repository", {})
            return healing_config.get("db_path", "data/healing_history.db")
        except FileNotFoundError:
            return "data/healing_history.db"

    def _get_session(self) -> Session:
        """Create a new database session."""
        return self._Session()

    def lookup(
        self,
        original_selector: str,
        strategy: str = "css",
        page_url: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Look up a cached healing for a broken locator.

        Args:
            original_selector: The broken selector string.
            strategy: Locator strategy ("css", "xpath", etc.).
            page_url: Optional page URL for context-specific lookups.

        Returns:
            Dict with healed selector info if found and not expired, else None.
        """
        session = self._get_session()
        try:
            query = session.query(HealingRecord).filter(
                HealingRecord.original_selector == original_selector,
                HealingRecord.original_strategy == strategy,
                HealingRecord.status == "healed",
                HealingRecord.decision == "auto_heal",
            )

            if page_url:
                query = query.filter(HealingRecord.page_url == page_url)

            # Get the most recent matching record
            record = query.order_by(HealingRecord.created_at.desc()).first()

            if record is None:
                return None

            # Check TTL
            if record.expires_at and datetime.utcnow() > record.expires_at:
                logger.debug(
                    "Cached healing expired for '%s' (expired at %s)",
                    original_selector, record.expires_at,
                )
                return None

            logger.info(
                "Cache HIT for locator '%s' -> '%s' (confidence=%.2f)",
                original_selector, record.healed_selector, record.confidence,
            )

            return {
                "healed_selector": record.healed_selector,
                "healed_strategy": record.healed_strategy,
                "confidence": record.confidence,
                "reasoning": record.reasoning,
                "cached": True,
                "original_heal_date": record.created_at.isoformat(),
            }

        finally:
            session.close()

    def save(
        self,
        original_selector: str,
        original_strategy: str,
        healed_selector: Optional[str],
        healed_strategy: Optional[str],
        confidence: float,
        reasoning: str,
        decision: str,
        test_name: Optional[str] = None,
        page_url: Optional[str] = None,
        element_intent: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_latency_ms: Optional[float] = None,
    ) -> int:
        """
        Save a healing result to the repository.

        Args:
            original_selector: The broken selector.
            original_strategy: Strategy of the broken selector.
            healed_selector: The replacement selector (None if rejected).
            healed_strategy: Strategy of the replacement.
            confidence: Confidence score (0.0 - 1.0).
            reasoning: LLM reasoning for the healing.
            decision: Healing decision ("auto_heal", "suggest", "reject").
            test_name: Name of the test that triggered healing.
            page_url: URL of the page being tested.
            element_intent: Description of what the element is for.
            llm_provider: Which LLM provider was used.
            llm_model: Which model was used.
            llm_latency_ms: LLM API latency in milliseconds.

        Returns:
            The ID of the saved record.
        """
        session = self._get_session()
        try:
            record = HealingRecord(
                original_selector=original_selector,
                original_strategy=original_strategy,
                healed_selector=healed_selector,
                healed_strategy=healed_strategy,
                confidence=confidence,
                reasoning=reasoning,
                decision=decision,
                test_name=test_name,
                page_url=page_url,
                element_intent=element_intent,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_latency_ms=llm_latency_ms,
                status="healed" if decision == "auto_heal" else "suggested",
                is_cached_hit=False,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=self.cache_ttl_hours),
            )

            session.add(record)
            session.commit()

            record_id = record.id
            logger.info(
                "Healing saved (id=%d): '%s' -> '%s' [%s, confidence=%.2f]",
                record_id, original_selector, healed_selector,
                decision, confidence,
            )

            # Also append to JSONL audit log
            self._append_audit_log(record)

            return record_id

        finally:
            session.close()

    def get_recent_healings(
        self, hours: int = 24, limit: int = 100
    ) -> list[dict]:
        """
        Get recent healing records for report generation.

        Args:
            hours: How many hours back to look.
            limit: Maximum number of records to return.

        Returns:
            List of healing record dicts, newest first.
        """
        session = self._get_session()
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            records = (
                session.query(HealingRecord)
                .filter(HealingRecord.created_at >= since)
                .order_by(HealingRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [r.to_dict() for r in records]
        finally:
            session.close()

    def get_all_healings(self) -> list[dict]:
        """Get all healing records (for comprehensive reports)."""
        session = self._get_session()
        try:
            records = (
                session.query(HealingRecord)
                .order_by(HealingRecord.created_at.desc())
                .all()
            )
            return [r.to_dict() for r in records]
        finally:
            session.close()

    def get_healing_stats(self) -> dict:
        """
        Get aggregate statistics for the healing report dashboard.

        Returns:
            Dict with counts, rates, and provider distribution.
        """
        session = self._get_session()
        try:
            total = session.query(HealingRecord).count()
            auto_healed = session.query(HealingRecord).filter(
                HealingRecord.decision == "auto_heal"
            ).count()
            suggested = session.query(HealingRecord).filter(
                HealingRecord.decision == "suggest"
            ).count()
            rejected = session.query(HealingRecord).filter(
                HealingRecord.decision == "reject"
            ).count()

            return {
                "total_attempts": total,
                "auto_healed": auto_healed,
                "suggested_for_review": suggested,
                "rejected": rejected,
                "heal_rate": auto_healed / total if total > 0 else 0.0,
            }
        finally:
            session.close()

    @staticmethod
    def _append_audit_log(record: HealingRecord):
        """Append a record to the JSONL audit log file."""
        try:
            import yaml
            with open(_CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            audit_config = config.get("healing", {}).get("audit_log", {})

            if not audit_config.get("enabled", True):
                return

            log_path = Path(audit_config.get("path", "data/healing_audit_log.jsonl"))
            log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(log_path, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")

        except Exception as e:
            logger.warning("Failed to append to audit log: %s", e)
