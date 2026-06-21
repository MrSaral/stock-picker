import yfinance as yf
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

def fetch_stock_details(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch current stock statistics and metadata using yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        # Fetch fast_info or info (info can be slow, fast_info is quicker for basic metrics)
        info = stock.info
        
        if not info or 'regularMarketPrice' not in info and 'currentPrice' not in info:
            # Fallback check
            history = stock.history(period="1d")
            if history.empty:
                return None
            current_price = float(history['Close'].iloc[-1])
            prev_close = float(history['Open'].iloc[-1]) # Rough fallback
        else:
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            prev_close = info.get('regularMarketPreviousClose') or info.get('previousClose')
        
        # Calculate daily change
        daily_change_pct = 0.0
        if current_price and prev_close:
            daily_change_pct = ((current_price - prev_close) / prev_close) * 100.0

        return {
            "ticker": ticker.upper(),
            "name": info.get('longName') or info.get('shortName') or ticker.upper(),
            "price": current_price,
            "previous_close": prev_close,
            "daily_change_percent": round(daily_change_pct, 2),
            "pe_ratio": info.get('trailingPE') or info.get('forwardPE'),
            "market_cap": info.get('marketCap'),
            "volume": info.get('volume') or info.get('regularMarketVolume'),
            "average_volume": info.get('averageVolume') or info.get('averageVolume10days'),
            "currency": info.get('currency', 'USD'),
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "summary": info.get('longBusinessSummary', '')
        }
    except Exception as e:
        logger.error(f"Error fetching data for ticker {ticker}: {e}")
        return None

def fetch_historical_performance(ticker: str, period: str = "7d") -> Dict[str, Any]:
    """
    Fetch historical performance to calculate price changes (returns).
    """
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)
        if history.empty or len(history) < 2:
            return {"ticker": ticker, "change_percent": 0.0, "volume_delta": 1.0}
        
        start_price = float(history['Close'].iloc[0])
        end_price = float(history['Close'].iloc[-1])
        change_percent = ((end_price - start_price) / start_price) * 100.0

        # Calculate volume delta: volume in period vs average volume
        avg_volume = float(history['Volume'].mean())
        last_volume = float(history['Volume'].iloc[-1])
        volume_delta = last_volume / avg_volume if avg_volume > 0 else 1.0

        return {
            "ticker": ticker.upper(),
            "change_percent": round(change_percent, 2),
            "volume_delta": round(volume_delta, 2),
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching history for {ticker}: {e}")
        return {"ticker": ticker, "change_percent": 0.0, "volume_delta": 1.0}

def compile_stock_candidates(tickers: List[str]) -> List[Dict[str, Any]]:
    """
    Compile stock data for a list of tickers to be analyzed by the LLM.
    Identifies biggest losers, P/E ratios, and trading volume deltas.
    """
    candidates = []
    for ticker in tickers:
        details = fetch_stock_details(ticker)
        if not details or details['price'] is None:
            continue
        
        # Fetch 7-day history for returns & volume delta
        history = fetch_historical_performance(ticker, period="7d")
        
        candidate_data = {
            **details,
            "weekly_change_percent": history["change_percent"],
            "volume_delta": history["volume_delta"]
        }
        candidates.append(candidate_data)
    
    return candidates
