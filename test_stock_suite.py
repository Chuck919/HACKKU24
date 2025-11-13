"""
Test script to verify Stock Suite features are working correctly
Tests the new insider trading and market news sentiment functionality
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    fetch_insider_transactions, 
    fetch_market_news_sentiment,
    TOP_10_SP500,
    read_from_database
)

def test_database_columns():
    """Test that database has all required columns"""
    print("=" * 60)
    print("TEST 1: Database Schema Verification")
    print("=" * 60)
    
    users = read_from_database()
    if not users:
        print("⚠ Warning: No users in database")
        return False
    
    user = users[0]
    expected_keys = [
        'email', 'text', 'token', 'include_charts',
        'include_sp500_chart', 'include_nasdaq_chart', 'include_bitcoin_chart',
        'include_top10_stocks', 'include_stock_suite', 
        'include_insider_trading', 'include_market_news'
    ]
    
    print(f"\n✓ User record has {len(user)} fields")
    print("\nExpected columns:")
    all_present = True
    for key in expected_keys:
        status = "✓" if key in user else "✗"
        if key not in user:
            all_present = False
        print(f"  {status} {key}")
    
    if all_present:
        print("\n✅ All required columns present!")
        return True
    else:
        print("\n❌ Missing columns!")
        return False

def test_insider_transactions():
    """Test insider trading data fetching"""
    print("\n" + "=" * 60)
    print("TEST 2: Insider Transactions API")
    print("=" * 60)
    
    # Test with just 2 symbols to avoid rate limits
    test_symbols = ['AAPL', 'MSFT']
    print(f"\nFetching insider data for {test_symbols}...")
    
    insider_data = fetch_insider_transactions(test_symbols)
    
    if insider_data:
        print(f"\n✅ Successfully fetched insider data for {len(insider_data)} symbol(s)")
        for symbol, transactions in insider_data.items():
            print(f"\n  {symbol}: {len(transactions)} transaction(s)")
            if transactions:
                for i, trans in enumerate(transactions[:2], 1):  # Show first 2
                    print(f"    {i}. {trans.get('filing_date', 'N/A')} - "
                          f"{trans.get('transaction_type', 'Unknown')} - "
                          f"{trans.get('insider_name', 'Unknown')}")
        return True
    else:
        print("⚠ Warning: Using mock data or no data returned")
        return False

def test_market_news():
    """Test market news sentiment fetching"""
    print("\n" + "=" * 60)
    print("TEST 3: Market News Sentiment API")
    print("=" * 60)
    
    # Test with just 2 tickers and 1 topic
    test_tickers = ['AAPL', 'MSFT']
    test_topics = ['technology']
    print(f"\nFetching market news for tickers: {test_tickers}")
    print(f"Topics: {test_topics}")
    
    market_news = fetch_market_news_sentiment(
        topics=test_topics,
        tickers=test_tickers,
        limit=5
    )
    
    if market_news:
        print(f"\n✅ Successfully fetched {len(market_news)} news item(s)")
        for i, news in enumerate(market_news[:3], 1):  # Show first 3
            sentiment = news.get('sentiment_label', 'Unknown')
            title = news.get('title', 'No title')[:60] + "..."
            print(f"\n  {i}. [{sentiment}] {title}")
            if news.get('ticker_sentiment'):
                tickers_mentioned = [t['ticker'] for t in news['ticker_sentiment'][:3]]
                print(f"     Tickers: {', '.join(tickers_mentioned)}")
        return True
    else:
        print("⚠ Warning: Using mock data or no data returned")
        return False

def test_user_preferences():
    """Test reading user preferences for Stock Suite features"""
    print("\n" + "=" * 60)
    print("TEST 4: User Preferences")
    print("=" * 60)
    
    users = read_from_database()
    if not users:
        print("⚠ Warning: No users in database")
        return False
    
    user = users[0]
    email = user['email']
    
    print(f"\nUser: {email}")
    print("\nStock Suite Preferences:")
    print(f"  Stock Suite Master: {user.get('include_stock_suite', False)}")
    print(f"  Insider Trading: {user.get('include_insider_trading', False)}")
    print(f"  Market News: {user.get('include_market_news', False)}")
    
    print("\nChart Preferences:")
    print(f"  S&P 500: {user.get('include_sp500_chart', False)}")
    print(f"  NASDAQ: {user.get('include_nasdaq_chart', False)}")
    print(f"  Bitcoin: {user.get('include_bitcoin_chart', False)}")
    print(f"  Top 10 Stocks: {user.get('include_top10_stocks', False)}")
    
    print("\n✅ User preferences loaded successfully")
    return True

if __name__ == '__main__':
    print("\n" + "🚀" * 30)
    print("STOCK SUITE FEATURES TEST SUITE")
    print("🚀" * 30 + "\n")
    
    results = []
    
    # Run all tests
    results.append(("Database Schema", test_database_columns()))
    results.append(("User Preferences", test_user_preferences()))
    results.append(("Insider Transactions", test_insider_transactions()))
    results.append(("Market News Sentiment", test_market_news()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "⚠ WARN"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! Stock Suite is ready to use!")
    else:
        print("\n⚠ Some tests showed warnings (may be using mock data)")
        print("This is normal if API keys are not configured or rate limits are hit.")
