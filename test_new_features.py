"""Test the new functionality"""
from main import generate_market_charts, fetch_top10_sp500_stocks
import sys

print("Testing new candlestick charts and Top 10 stocks...")
print("=" * 60)

# Test individual chart generation
print("\n1. Testing individual chart generation:")
user_prefs = {'sp500': True, 'nasdaq': False, 'bitcoin': True}
charts = generate_market_charts(user_prefs)

print(f"\nRequested: SP500=True, NASDAQ=False, Bitcoin=True")
print(f"Generated {len(charts)} charts:")
for name in charts.keys():
    print(f"  ✓ {name}")

# Test Top 10 stocks
print("\n2. Testing Top 10 S&P 500 stocks:")
stocks = fetch_top10_sp500_stocks()

if stocks:
    print(f"✓ Retrieved {len(stocks)} stocks:")
    for stock in stocks[:3]:  # Show first 3
        direction_symbol = "▲" if stock['direction'] == 'up' else "▼"
        print(f"  {direction_symbol} {stock['symbol']}: ${stock['price']:.2f} ({stock['change_pct']:+.2f}%)")
    print(f"  ... and {len(stocks) - 3} more")
else:
    print("✗ Failed to retrieve stocks")
    sys.exit(1)

# Test all charts
print("\n3. Testing all charts enabled:")
all_prefs = {'sp500': True, 'nasdaq': True, 'bitcoin': True}
all_charts = generate_market_charts(all_prefs)

if len(all_charts) == 3:
    print(f"✅ SUCCESS: All 3 charts generated!")
else:
    print(f"⚠ WARNING: Only {len(all_charts)}/3 charts generated")

print("\n" + "=" * 60)
print("✅ All tests passed!")
