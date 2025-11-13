"""
Test script to check Alpha Vantage API for Top 10 S&P 500 stocks
Tests each ticker individually with proper rate limiting
"""

import requests
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Top 10 S&P 500 stocks by index weight (as of 2024)
TOP_10_SP500 = [
    ('AAPL', 'Apple', 7.1),           # ~7.1% weight
    ('MSFT', 'Microsoft', 6.8),       # ~6.8% weight  
    ('NVDA', 'NVIDIA', 6.2),          # ~6.2% weight
    ('AMZN', 'Amazon', 3.8),          # ~3.8% weight
    ('META', 'Meta', 2.6),            # ~2.6% weight
    ('GOOGL', 'Alphabet A', 2.1),     # ~2.1% weight
    ('TSLA', 'Tesla', 1.8),           # ~1.8% weight
    ('BRK.B', 'Berkshire B', 1.7),    # ~1.7% weight
    ('LLY', 'Eli Lilly', 1.5),        # ~1.5% weight
    ('AVGO', 'Broadcom', 1.4)         # ~1.4% weight
]

def test_alpha_vantage_stock(symbol, name, weight):
    """Test fetching a single stock from Alpha Vantage"""
    api_key = os.getenv('ALPHAVANTAGE_API_KEY')
    
    if not api_key:
        print("ERROR: ALPHAVANTAGE_API_KEY not found in environment")
        return None
    
    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': api_key
    }
    
    try:
        print(f"\n{'='*60}")
        print(f"Testing: {symbol} ({name}) - Weight: {weight}%")
        print(f"{'='*60}")
        
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")
            
            # Check for error messages
            if 'Error Message' in data:
                print(f"ERROR: {data['Error Message']}")
                return None
            
            # Check for rate limit message
            if 'Note' in data:
                print(f"RATE LIMIT: {data['Note']}")
                return None
            
            # Check for Information message
            if 'Information' in data:
                print(f"INFO: {data['Information']}")
                return None
            
            # Get the quote data
            if 'Global Quote' in data:
                quote = data['Global Quote']
                
                if not quote:
                    print("WARNING: Global Quote is empty")
                    return None
                
                print(f"\nQuote Data:")
                for key, value in quote.items():
                    print(f"  {key}: {value}")
                
                # Extract price and calculate change
                if '05. price' in quote and '08. previous close' in quote:
                    try:
                        current_price = float(quote['05. price'])
                        prev_close = float(quote['08. previous close'])
                        change_percent = ((current_price - prev_close) / prev_close) * 100
                        
                        print(f"\nSUCCESS:")
                        print(f"  Current Price: ${current_price:.2f}")
                        print(f"  Previous Close: ${prev_close:.2f}")
                        print(f"  Change: {change_percent:+.2f}%")
                        
                        return {
                            'symbol': symbol,
                            'name': name,
                            'weight': weight,
                            'price': current_price,
                            'change_percent': change_percent
                        }
                    except (ValueError, KeyError) as e:
                        print(f"ERROR: Could not parse price data: {e}")
                        return None
                else:
                    print("ERROR: Required price fields not found in quote")
                    return None
            else:
                print("ERROR: 'Global Quote' not found in response")
                print(f"Full Response: {data}")
                return None
        else:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("="*60)
    print("Alpha Vantage API Test - Top 10 S&P 500 Stocks")
    print("Testing with proper rate limiting (5 calls/minute)")
    print("Expected duration: ~5 minutes")
    print("="*60)
    
    results = []
    
    for idx, (symbol, name, weight) in enumerate(TOP_10_SP500, 1):
        result = test_alpha_vantage_stock(symbol, name, weight)
        
        if result:
            results.append(result)
        
        # Rate limiting: 5 calls per minute = 30 seconds per call for safety
        if idx < len(TOP_10_SP500):
            wait_time = 30  # 30 seconds to be safe
            print(f"\nWaiting {wait_time} seconds before next request...")
            print(f"Progress: {idx}/{len(TOP_10_SP500)} stocks tested")
            time.sleep(wait_time)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Successfully fetched: {len(results)}/{len(TOP_10_SP500)} stocks")
    
    if results:
        print("\nSuccessful Results (ordered by S&P 500 weight):")
        print(f"{'Symbol':<8} {'Name':<15} {'Weight':<8} {'Price':<12} {'Change':<10}")
        print("-"*60)
        for r in results:
            print(f"{r['symbol']:<8} {r['name']:<15} {r['weight']:.1f}%     ${r['price']:<10.2f} {r['change_percent']:+.2f}%")
    else:
        print("\nNo successful results")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    main()
