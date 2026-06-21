import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_db
from backend.app.database import Base, MonitoredStock, WeeklyRecommendation
from backend.app import stock_service

# Setup in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency override
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# Mock yfinance responses to run tests fast and offline
@pytest.fixture(autouse=True)
def mock_stock_service(monkeypatch):
    def mock_fetch_details(ticker):
        ticker_upper = ticker.upper()
        if ticker_upper == "INVALID":
            return None
        return {
            "ticker": ticker_upper,
            "name": f"Mock {ticker_upper} Corp",
            "price": 150.0,
            "previous_close": 148.0,
            "daily_change_percent": 1.35,
            "pe_ratio": 25.4,
            "market_cap": 1000000000,
            "volume": 5000000,
            "average_volume": 4500000,
            "currency": "USD",
            "sector": "Technology",
            "industry": "Software",
            "summary": "Mock business summary description."
        }
        
    def mock_compile_candidates(tickers):
        return [
            {
                "ticker": t.upper(),
                "name": f"Mock {t.upper()} Corp",
                "price": 100.0 + i,
                "previous_close": 98.0,
                "daily_change_percent": 2.0,
                "pe_ratio": 15.0 + i,
                "market_cap": 500000000,
                "volume": 2000000,
                "average_volume": 2000000,
                "currency": "USD",
                "sector": "Tech",
                "industry": "Software",
                "summary": "Summary",
                "weekly_change_percent": -5.0 if i == 0 else 2.5,  # First is loser
                "volume_delta": 1.5 if i == 1 else 1.0  # Second has volume delta
            }
            for i, t in enumerate(tickers)
        ]

    monkeypatch.setattr(stock_service, "fetch_stock_details", mock_fetch_details)
    monkeypatch.setattr(stock_service, "compile_stock_candidates", mock_compile_candidates)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Stock Picker & Monitor API"}

def test_add_monitored_stock():
    # Adding a valid stock
    response = client.post(
        "/api/monitored-stocks",
        json={"ticker": "aapl", "price_threshold": 160.0, "alert_condition": "above", "cadence_days": 5}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["name"] == "Mock AAPL Corp"
    assert data["price_threshold"] == 160.0
    assert data["alert_condition"] == "above"
    assert data["cadence_days"] == 5

    # Adding an invalid stock
    response = client.post(
        "/api/monitored-stocks",
        json={"ticker": "invalid"}
    )
    assert response.status_code == 400
    assert "Invalid stock ticker" in response.json()["detail"]

    # Adding duplicate
    response = client.post(
        "/api/monitored-stocks",
        json={"ticker": "aapl"}
    )
    assert response.status_code == 400
    assert "already being monitored" in response.json()["detail"]

def test_get_monitored_stocks():
    # Insert one stock directly
    db = TestingSessionLocal()
    stock = MonitoredStock(ticker="MSFT", name="Mock MSFT Corp", alert_condition="below", price_threshold=300.0, cadence_days=3)
    db.add(stock)
    db.commit()
    db.close()

    response = client.get("/api/monitored-stocks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "MSFT"
    assert data[0]["alert_condition"] == "below"
    assert data[0]["current_price"] == 150.0  # From mock

def test_update_monitored_stock():
    db = TestingSessionLocal()
    stock = MonitoredStock(ticker="GOOGL", name="Mock GOOGL Corp", alert_condition="none", cadence_days=7)
    db.add(stock)
    db.commit()
    db.close()

    response = client.put(
        "/api/monitored-stocks/googl",
        json={"price_threshold": 180.0, "alert_condition": "above", "cadence_days": 1}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["price_threshold"] == 180.0
    assert data["alert_condition"] == "above"
    assert data["cadence_days"] == 1

def test_delete_monitored_stock():
    db = TestingSessionLocal()
    stock = MonitoredStock(ticker="TSLA", name="Mock TSLA Corp")
    db.add(stock)
    db.commit()
    db.close()

    # Delete
    response = client.delete("/api/monitored-stocks/tsla")
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully stopped monitoring TSLA"

    # Delete non-existent
    response = client.delete("/api/monitored-stocks/tsla")
    assert response.status_code == 404

def test_generate_weekly_recommendation():
    # Seed db with monitored stocks so there are candidates
    db = TestingSessionLocal()
    db.add(MonitoredStock(ticker="AAPL"))
    db.add(MonitoredStock(ticker="MSFT"))
    db.commit()
    db.close()

    response = client.post("/api/weekly-recommendations/generate")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] in ["AAPL", "MSFT"]
    assert data["reasoning"] != ""
    assert data["criteria"] in ["biggest_loser", "underrated", "news_delta"]

def test_alert_check_trigger():
    db = TestingSessionLocal()
    # AAPL is current price 150 (mock). Alert above 140. Alert should trigger!
    db.add(MonitoredStock(ticker="AAPL", alert_condition="above", price_threshold=140.0, cadence_days=0))
    # MSFT is current price 150 (mock). Alert below 100. Alert should NOT trigger!
    db.add(MonitoredStock(ticker="MSFT", alert_condition="below", price_threshold=100.0, cadence_days=0))
    # GOOGL has cadence alert (cadence 1, last_notified is None) -> Should trigger!
    db.add(MonitoredStock(ticker="GOOGL", alert_condition="none", cadence_days=1, last_notified_at=None))
    db.commit()
    db.close()

    response = client.post("/api/test-alert-check")
    assert response.status_code == 200
    data = response.json()
    assert data["checked_count"] == 3
    assert data["triggered_count"] == 2
    
    triggered_tickers = [a["ticker"] for a in data["triggered_alerts"]]
    assert "AAPL" in triggered_tickers
    assert "GOOGL" in triggered_tickers
    assert "MSFT" not in triggered_tickers
