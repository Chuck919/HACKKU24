"""
Simple test to diagnose yfinance issues
"""
import yfinance as yf
from datetime import datetime, timedelta

print("Testing yfinance connection...")
print("=" * 50)

# Test 1: Simple ticker info
print("\n1. Testing basic ticker info:")
try:
    ticker = yf.Ticker("AAPL")
    info = ticker.info
    print(f"✓ Apple stock info retrieved: {info.get('symbol', 'N/A')}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 2: Historical data with period
print("\n2. Testing historical data (period='1mo'):")
try:
    ticker = yf.Ticker("AAPL")
    hist = ticker.history(period="1mo")
    print(f"✓ Got {len(hist)} days of data")
    if len(hist) > 0:
        print(f"  Latest close: ${hist['Close'].iloc[-1]:.2f}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 3: Download method
print("\n3. Testing yf.download():")
try:
    data = yf.download("AAPL", period="1mo", progress=False)
    print(f"✓ Got {len(data)} days of data")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 4: Index tickers
print("\n4. Testing index tickers:")
for name, ticker_symbol in [("S&P 500", "^GSPC"), ("NASDAQ", "^IXIC"), ("Bitcoin", "BTC-USD")]:
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="5d")
        if len(hist) > 0:
            print(f"✓ {name} ({ticker_symbol}): {len(hist)} days")
        else:
            print(f"✗ {name} ({ticker_symbol}): No data")
    except Exception as e:
        print(f"✗ {name} ({ticker_symbol}): {str(e)[:60]}")

print("\n" + "=" * 50)
print("Test complete!")
