import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database path (local SQLite file)
DATABASE_URL = "sqlite:///./stock_picker.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MonitoredStock(Base):
    __tablename__ = "monitored_stocks"

    ticker = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    
    # Alert conditions
    price_threshold = Column(Float, nullable=True)  # Alert target price
    alert_condition = Column(String, default="none")  # 'above', 'below', or 'none'
    
    # Cadence conditions
    cadence_days = Column(Integer, default=7)  # Notify once every X days (0 for no cadence limit)
    last_notified_at = Column(DateTime, nullable=True)  # Timestamp of last notification email
    
    # Metadata
    added_at = Column(DateTime, default=datetime.utcnow)

class WeeklyRecommendation(Base):
    __tablename__ = "weekly_recommendations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    week_start_date = Column(String, index=True)  # Format: YYYY-MM-DD (typically Monday of that week)
    ticker = Column(String, nullable=False)
    name = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=False)
    criteria = Column(String, nullable=True)  # e.g., 'biggest_loser', 'underrated', 'news_delta'
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
