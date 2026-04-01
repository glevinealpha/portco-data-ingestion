"""
Database read/write layer — SQLite via SQLAlchemy.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, DateTime,
    Text, UniqueConstraint, inspect
)
from sqlalchemy.orm import DeclarativeBase, Session

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "alphafmc.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False)


class Base(DeclarativeBase):
    pass


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    portco_id       = Column(String(10), nullable=False, index=True)
    portco_name     = Column(String(100))
    period          = Column(String(20), nullable=False)
    quarter         = Column(String(5))
    year            = Column(Integer)
    currency        = Column(String(5))
    revenue         = Column(Float)
    gross_profit    = Column(Float)
    ebitda          = Column(Float)
    ebit            = Column(Float)
    net_income      = Column(Float)
    cash            = Column(Float)
    total_debt      = Column(Float)
    net_debt        = Column(Float)
    total_assets    = Column(Float)
    headcount       = Column(Integer)
    revenue_growth_yoy   = Column(Float)
    ebitda_margin        = Column(Float)
    net_debt_ebitda      = Column(Float)
    vs_budget_revenue_pct  = Column(Float)
    vs_budget_ebitda_pct   = Column(Float)
    extraction_confidence  = Column(Float, default=1.0)
    extracted_at           = Column(String(50))
    source_pdf             = Column(String(255))
    raw_extraction         = Column(Text)  # JSON blob from Claude

    __table_args__ = (
        UniqueConstraint("portco_id", "period", name="uq_portco_period"),
    )


def init_db() -> None:
    Base.metadata.create_all(ENGINE)


def upsert_record(data: dict) -> None:
    """Insert or replace a financial record."""
    init_db()
    with Session(ENGINE) as session:
        existing = (
            session.query(FinancialRecord)
            .filter_by(portco_id=data["portco_id"], period=data["period"])
            .first()
        )
        if existing:
            for key, val in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, val)
        else:
            rec = FinancialRecord(**{k: v for k, v in data.items()
                                     if hasattr(FinancialRecord, k)})
            session.add(rec)
        session.commit()


def bulk_load_from_json(json_path: Path) -> int:
    """Load all records from the financials.json manifest."""
    init_db()
    with open(json_path) as f:
        records = json.load(f)

    count = 0
    for rec in records:
        rec.setdefault("extracted_at", datetime.utcnow().isoformat())
        rec.setdefault("extraction_confidence", 1.0)
        upsert_record(rec)
        count += 1
    return count


def get_all_records() -> list[dict]:
    init_db()
    with Session(ENGINE) as session:
        rows = session.query(FinancialRecord).order_by(
            FinancialRecord.portco_id,
            FinancialRecord.year,
            FinancialRecord.quarter
        ).all()
        return [_row_to_dict(r) for r in rows]


def get_portco_records(portco_id: str) -> list[dict]:
    init_db()
    with Session(ENGINE) as session:
        rows = session.query(FinancialRecord).filter_by(
            portco_id=portco_id
        ).order_by(FinancialRecord.year, FinancialRecord.quarter).all()
        return [_row_to_dict(r) for r in rows]


def get_latest_records() -> list[dict]:
    """Return the most recent quarter for each portco."""
    init_db()
    with Session(ENGINE) as session:
        # Get max period per portco
        from sqlalchemy import func
        subq = (
            session.query(
                FinancialRecord.portco_id,
                func.max(FinancialRecord.year * 10 +
                         func.cast(func.substr(FinancialRecord.quarter, 2), Integer)
                         ).label("max_period_key")
            ).group_by(FinancialRecord.portco_id).subquery()
        )
        rows = []
        for portco_id, _ in session.query(subq).all():
            latest = (
                session.query(FinancialRecord)
                .filter_by(portco_id=portco_id)
                .order_by(
                    FinancialRecord.year.desc(),
                    FinancialRecord.quarter.desc()
                )
                .first()
            )
            if latest:
                rows.append(_row_to_dict(latest))
        return rows


def _row_to_dict(row: FinancialRecord) -> dict:
    return {c.key: getattr(row, c.key)
            for c in inspect(row).mapper.column_attrs}


if __name__ == "__main__":
    json_path = Path(__file__).parent.parent / "data" / "financials.json"
    count = bulk_load_from_json(json_path)
    print(f"Loaded {count} records into {DB_PATH}")
