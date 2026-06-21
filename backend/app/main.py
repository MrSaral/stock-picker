import os
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.app.database import init_db, get_db, MonitoredStock, WeeklyRecommendation
from backend.app.stock_service import fetch_stock_details, compile_stock_candidates

# Initialize FastAPI App
app = FastAPI(title="Stock Picker & Monitor API")

# Add CORS Middleware to support Vite Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on Startup
@app.on_event("startup")
def on_startup():
    init_db()

# Pydantic Schemas
class StockCreateSchema(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g. AAPL)")
    price_threshold: Optional[float] = Field(None, description="Price threshold for alert")
    alert_condition: Optional[str] = Field("none", description="Alert condition: 'above', 'below', or 'none'")
    cadence_days: Optional[int] = Field(7, description="Notify once every X days (0 for no cadence limit)")

    class Config:
        from_attributes = True

class StockUpdateSchema(BaseModel):
    price_threshold: Optional[float] = None
    alert_condition: Optional[str] = "none"
    cadence_days: Optional[int] = 7

class StockResponseSchema(BaseModel):
    ticker: str
    name: Optional[str]
    price_threshold: Optional[float]
    alert_condition: str
    cadence_days: int
    last_notified_at: Optional[datetime]
    added_at: datetime
    # Joined real-time data
    current_price: Optional[float] = None
    daily_change_percent: Optional[float] = None

    class Config:
        from_attributes = True

class RecommendationResponseSchema(BaseModel):
    id: int
    week_start_date: str
    ticker: str
    name: Optional[str]
    price: Optional[float]
    reasoning: str
    criteria: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Helper to enrich monitored stock database records with real-time yfinance info
def enrich_stock_data(db_stock: MonitoredStock) -> StockResponseSchema:
    details = fetch_stock_details(db_stock.ticker)
    current_price = details["price"] if details else None
    daily_change = details["daily_change_percent"] if details else None
    
    return StockResponseSchema(
        ticker=db_stock.ticker,
        name=db_stock.name or (details["name"] if details else db_stock.ticker),
        price_threshold=db_stock.price_threshold,
        alert_condition=db_stock.alert_condition,
        cadence_days=db_stock.cadence_days,
        last_notified_at=db_stock.last_notified_at,
        added_at=db_stock.added_at,
        current_price=current_price,
        daily_change_percent=daily_change
    )

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Welcome to Stock Picker & Monitor API"}

@app.get("/api/stock-details/{ticker}", response_model=dict)
def get_realtime_stock_details(ticker: str):
    """
    Query real-time stock details from Yahoo Finance.
    """
    details = fetch_stock_details(ticker)
    if not details:
        raise HTTPException(status_code=404, detail="Stock ticker not found or API error")
    return details

@app.get("/api/monitored-stocks", response_model=List[StockResponseSchema])
def get_monitored_stocks(db: Session = Depends(get_db)):
    """
    Get all stocks being monitored, enriched with current price.
    """
    stocks = db.query(MonitoredStock).all()
    # Enrich with real-time stock data
    return [enrich_stock_data(s) for s in stocks]

@app.post("/api/monitored-stocks", response_model=StockResponseSchema)
def add_monitored_stock(stock_data: StockCreateSchema, db: Session = Depends(get_db)):
    """
    Add a stock to monitor. Fetches company name from yfinance first.
    """
    ticker_upper = stock_data.ticker.upper().strip()
    
    # Check if already monitored
    existing = db.query(MonitoredStock).filter(MonitoredStock.ticker == ticker_upper).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"{ticker_upper} is already being monitored.")
    
    # Check if valid ticker
    details = fetch_stock_details(ticker_upper)
    if not details:
        raise HTTPException(status_code=400, detail=f"Invalid stock ticker: {ticker_upper}")
        
    db_stock = MonitoredStock(
        ticker=ticker_upper,
        name=details["name"],
        price_threshold=stock_data.price_threshold,
        alert_condition=stock_data.alert_condition,
        cadence_days=stock_data.cadence_days,
        last_notified_at=None
    )
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    
    return enrich_stock_data(db_stock)

@app.put("/api/monitored-stocks/{ticker}", response_model=StockResponseSchema)
def update_monitored_stock(ticker: str, update_data: StockUpdateSchema, db: Session = Depends(get_db)):
    """
    Update monitoring settings (price alerts, cadence) for a stock.
    """
    ticker_upper = ticker.upper().strip()
    db_stock = db.query(MonitoredStock).filter(MonitoredStock.ticker == ticker_upper).first()
    if not db_stock:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    db_stock.price_threshold = update_data.price_threshold
    db_stock.alert_condition = update_data.alert_condition
    db_stock.cadence_days = update_data.cadence_days
    
    db.commit()
    db.refresh(db_stock)
    return enrich_stock_data(db_stock)

@app.delete("/api/monitored-stocks/{ticker}")
def delete_monitored_stock(ticker: str, db: Session = Depends(get_db)):
    """
    Stop monitoring a stock.
    """
    ticker_upper = ticker.upper().strip()
    db_stock = db.query(MonitoredStock).filter(MonitoredStock.ticker == ticker_upper).first()
    if not db_stock:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    db.delete(db_stock)
    db.commit()
    return {"message": f"Successfully stopped monitoring {ticker_upper}"}

@app.get("/api/weekly-recommendations", response_model=List[RecommendationResponseSchema])
def get_weekly_recommendations(db: Session = Depends(get_db)):
    """
    Retrieve previous weekly picks, sorted by latest date.
    """
    return db.query(WeeklyRecommendation).order_by(WeeklyRecommendation.created_at.desc()).all()

@app.post("/api/weekly-recommendations/generate", response_model=RecommendationResponseSchema)
def generate_weekly_recommendation(db: Session = Depends(get_db)):
    """
    Trigger LLM evaluation to pick a stock for this week.
    Since API keys are not supplied yet, we'll write the stub structure that evaluates candidates and picks one.
    """
    # Find candidates
    monitored = db.query(MonitoredStock).all()
    candidate_tickers = [m.ticker for m in monitored]
    
    # Fallback to some popular tickers if user hasn't added any yet
    if not candidate_tickers:
        candidate_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]
        
    candidates = compile_stock_candidates(candidate_tickers)
    if not candidates:
        raise HTTPException(status_code=400, detail="Unable to retrieve details for any candidates.")
        
    # Standard recommendation generation flow
    # Check if Gemini API key exists
    api_key = os.getenv("GEMINI_API_KEY")
    
    selected_candidate = None
    reasoning = ""
    criteria = "underrated"
    
    # 1. LLM logic actual run
    if api_key:
        try:
            import logging
            logger = logging.getLogger(__name__)
            from backend.app.stock_service import generate_gemini_recommendation
            gemini_rec = generate_gemini_recommendation(candidates, api_key)
            
            # Find the corresponding candidate detail in our compiled list
            rec_ticker = gemini_rec["ticker"].upper()
            selected_candidate = next((c for c in candidates if c["ticker"] == rec_ticker), None)
            
            if selected_candidate:
                criteria = gemini_rec["criteria"]
                reasoning = gemini_rec["reasoning"]
            else:
                # If LLM selected a ticker outside the list, create a dummy selected candidate representation
                # using the returned ticker
                details = fetch_stock_details(rec_ticker)
                if details:
                    selected_candidate = details
                    criteria = gemini_rec["criteria"]
                    reasoning = gemini_rec["reasoning"]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error generating recommendation from Gemini: {e}")
            pass
            
    # Simple rule-based picker fallback (if Gemini API key is missing or failed)
    if not selected_candidate:
        try:
            # Try to find a stock with lowest positive PE
            underrated = sorted([c for c in candidates if c.get('pe_ratio') and c['pe_ratio'] > 0], key=lambda x: x['pe_ratio'])
            biggest_loser = sorted(candidates, key=lambda x: x.get('weekly_change_percent', 0.0))
            high_volume = sorted(candidates, key=lambda x: x.get('volume_delta', 1.0), reverse=True)
            
            # Let's pick biggest weekly loser if it dropped > 3%, else lowest PE, else high volume
            if biggest_loser and biggest_loser[0].get('weekly_change_percent', 0.0) < -3.0:
                selected_candidate = biggest_loser[0]
                criteria = "biggest_loser"
                reasoning = (
                    f"Selected {selected_candidate['name']} ({selected_candidate['ticker']}) because it experienced a significant weekly drop of "
                    f"{selected_candidate['weekly_change_percent']}%, and represents a potentially oversold entry opportunity. Current price is "
                    f"{selected_candidate['price']} {selected_candidate['currency']}."
                )
            elif underrated:
                selected_candidate = underrated[0]
                criteria = "underrated"
                reasoning = (
                    f"Selected {selected_candidate['name']} ({selected_candidate['ticker']}) due to its highly attractive valuation with a P/E "
                    f"ratio of {selected_candidate['pe_ratio']}. Solid financials suggest this stock is undervalued at the current market price of "
                    f"{selected_candidate['price']} {selected_candidate['currency']}."
                )
            else:
                selected_candidate = high_volume[0]
                criteria = "news_delta"
                reasoning = (
                    f"Selected {selected_candidate['name']} ({selected_candidate['ticker']}) based on a spike in trading volume delta of "
                    f"{selected_candidate['volume_delta']}x above average. This significant trade delta suggests high market interest and potential "
                    f"short-term upward momentum. Current price is {selected_candidate['price']} {selected_candidate['currency']}."
                )
        except Exception as e:
            # Fallback to simple selection
            selected_candidate = candidates[0]
            criteria = "underrated"
            reasoning = f"Selected {selected_candidate['name']} based on standard valuation metrics. Price: {selected_candidate['price']}."

    # Date string format
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    db_rec = WeeklyRecommendation(
        week_start_date=today_str,
        ticker=selected_candidate['ticker'],
        name=selected_candidate['name'],
        price=selected_candidate['price'],
        reasoning=reasoning,
        criteria=criteria
    )
    db.add(db_rec)
    db.commit()
    db.refresh(db_rec)
    
    return db_rec

@app.post("/api/test-alert-check")
def test_alert_check(db: Session = Depends(get_db)):
    """
    Trigger manual check for alert conditions on all monitored stocks.
    Runs conditions check:
    - Price threshold breach (above/below)
    - Cadence checking (if X days elapsed since last notification)
    Returns list of alerts triggered (stubs email sending).
    """
    stocks = db.query(MonitoredStock).all()
    triggered_alerts = []
    
    for stock in stocks:
        details = fetch_stock_details(stock.ticker)
        if not details or details['price'] is None:
            continue
            
        current_price = details['price']
        alert_triggered = False
        reason = ""
        
        # 1. Price threshold checks
        if stock.alert_condition == "above" and stock.price_threshold is not None:
            if current_price > stock.price_threshold:
                alert_triggered = True
                reason = f"Price {current_price} crossed above threshold {stock.price_threshold}."
        elif stock.alert_condition == "below" and stock.price_threshold is not None:
            if current_price < stock.price_threshold:
                alert_triggered = True
                reason = f"Price {current_price} crossed below threshold {stock.price_threshold}."
                
        # 2. Cadence check
        # Check if cadence is set (e.g. 7 days) and if that time has elapsed
        if stock.cadence_days and stock.cadence_days > 0:
            if stock.last_notified_at is None:
                # First time notification or not notified yet
                alert_triggered = True
                reason += f" Scheduled cadence alert (every {stock.cadence_days} days)."
            else:
                days_since = (datetime.utcnow() - stock.last_notified_at).days
                if days_since >= stock.cadence_days:
                    alert_triggered = True
                    reason += f" Cadence interval of {stock.cadence_days} days reached."
                    
        if alert_triggered:
            triggered_alerts.append({
                "ticker": stock.ticker,
                "name": stock.name,
                "current_price": current_price,
                "condition": stock.alert_condition,
                "threshold": stock.price_threshold,
                "reason": reason.strip()
            })
            # Update last notified timestamp in DB
            stock.last_notified_at = datetime.utcnow()
            
    if triggered_alerts:
        db.commit()
        try:
            from backend.app.notifier import send_email, build_alerts_html
            html_content = build_alerts_html(triggered_alerts)
            send_email("🔔 Stock Picker Alert Update", html_content)
        except Exception as e:
            # Log error but don't fail the request
            pass
        
    return {
        "checked_count": len(stocks),
        "triggered_count": len(triggered_alerts),
        "triggered_alerts": triggered_alerts
    }
