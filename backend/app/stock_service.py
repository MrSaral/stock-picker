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

from pydantic import BaseModel, Field

class GeminiRecommendationSchema(BaseModel):
    ticker: str = Field(..., description="The ticker symbol of the chosen stock, in uppercase.")
    criteria: str = Field(..., description="The strategy criteria used for choice: must be one of 'biggest_loser', 'underrated', or 'news_delta'.")
    reasoning: str = Field(..., description="A detailed financial analysis explaining why this stock was selected under the given criteria, including key stats.")

def generate_gemini_recommendation(candidates: List[Dict[str, Any]], api_key: str) -> Dict[str, Any]:
    """
    Query the Gemini API to analyze stock candidates and pick the best one for this week.
    """
    from google import genai
    from google.genai import types
    import json

    client = genai.Client(api_key=api_key)
    
    candidates_str = ""
    for c in candidates:
        candidates_str += (
            f"- Ticker: {c['ticker']}, Name: {c['name']}, Price: {c['price']} {c['currency']}\n"
            f"  P/E Ratio: {c.get('pe_ratio') or 'N/A'}, 7d Price Change: {c.get('weekly_change_percent') or 0.0}%\n"
            f"  7d Volume Delta: {c.get('volume_delta') or 1.0}x, Sector: {c.get('sector') or 'N/A'}, Industry: {c.get('industry') or 'N/A'}\n"
            f"  Description: {c.get('summary', '')[:120]}...\n\n"
        )
        
    prompt = f"""
You are an expert quantitative stock trader and financial advisor.
Your goal is to select the single best stock recommendation for this week from the following list of candidates:

{candidates_str}

Choose the stock that fits best into one of these three strategies:
1. "biggest_loser": Experienced a notable weekly price drop but remains fundamentally stable, suggesting a strong contrarian/oversold buy opportunity.
2. "underrated": Trade at a low P/E ratio, showing solid underlying value/earnings.
3. "news_delta": Experienced a trading volume spike (volume delta > 1.0) indicating a strong catalyst/momentum change in the news.

Analyze all options and return your selection. You must pick exactly one ticker.
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiRecommendationSchema,
            temperature=0.2,
        ),
    )
    
    result = json.loads(response.text)
    return result

