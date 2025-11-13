# fetch_stocks_batch.py
"""
Batch fetcher for Top 10 stocks - fetches 5 stocks at a time to avoid timeouts
This should be run as 2 separate scheduled tasks on PythonAnywhere
"""

from flask import Flask
from config import Config
import http.client
import urllib.parse
import json
import sqlite3
import os

app = Flask(__name__)
app.config.from_object(Config)

TOP_10_SP500 = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'META', 'GOOGL', 'TSLA', 'BRK.B', 'LLY', 'AVGO']

def fetch_and_cache_batch(start_idx, end_idx):
    """
    Fetch a batch of stocks and cache them in a temporary database
    """
    print(f"Fetching stocks {start_idx+1} to {end_idx}...")
    
    api_key = app.config.get('ALPHAVANTAGE_API_KEY')
    if not api_key:
        print("ERROR: No API key configured")
        return
    
    # Create/connect to cache database
    cache_db = 'instance/stock_cache.db'
    os.makedirs('instance', exist_ok=True)
    
    conn = sqlite3.connect(cache_db)
    cursor = conn.cursor()
    
    # Create cache table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_cache (
            symbol TEXT PRIMARY KEY,
            price REAL,
            previous_close REAL,
            change_pct REAL,
            direction TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    batch = TOP_10_SP500[start_idx:end_idx]
    
    for idx, symbol in enumerate(batch):
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': api_key
            }
            
            http_conn = http.client.HTTPSConnection('www.alphavantage.co', timeout=10)
            query_string = urllib.parse.urlencode(params)
            http_conn.request('GET', f'/query?{query_string}')
            
            response = http_conn.getresponse()
            data = json.loads(response.read().decode('utf-8'))
            http_conn.close()
            
            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                current_price = float(quote.get('05. price', 0))
                previous_close = float(quote.get('08. previous close', 0))
                
                if current_price > 0 and previous_close > 0:
                    daily_change = current_price - previous_close
                    daily_change_pct = (daily_change / previous_close) * 100
                    direction = 'up' if daily_change >= 0 else 'down'
                    
                    # Insert or update cache
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_cache 
                        (symbol, price, previous_close, change_pct, direction, timestamp)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (symbol, current_price, previous_close, daily_change_pct, direction))
                    
                    print(f"  SUCCESS: {symbol}: ${current_price:.2f} ({daily_change_pct:+.2f}%)")
                else:
                    print(f"  WARNING: {symbol}: Invalid price data")
            else:
                print(f"  WARNING: {symbol}: No data returned")
            
            # Only sleep between calls within the same batch, not after the last one
            if idx < len(batch) - 1:
                import time
                print(f"  Waiting 13 seconds...")
                time.sleep(13)
                
        except Exception as e:
            print(f"  ERROR: {symbol} failed: {e}")
            continue
    
    conn.commit()
    conn.close()
    print(f"Batch complete. Cached {len(batch)} stocks.")

if __name__ == '__main__':
    import sys
    
    # Usage: python fetch_stocks_batch.py <batch_number>
    # batch_number: 1 for stocks 0-5, 2 for stocks 5-10
    
    if len(sys.argv) > 1:
        batch = int(sys.argv[1])
        if batch == 1:
            fetch_and_cache_batch(0, 5)  # First 5 stocks
        elif batch == 2:
            fetch_and_cache_batch(5, 10)  # Last 5 stocks
        else:
            print("ERROR: Invalid batch number. Use 1 or 2.")
    else:
        print("Usage: python fetch_stocks_batch.py <batch_number>")
        print("  batch_number 1: Fetch stocks 1-5 (AAPL, MSFT, NVDA, AMZN, META)")
        print("  batch_number 2: Fetch stocks 6-10 (GOOGL, TSLA, BRK.B, LLY, AVGO)")
