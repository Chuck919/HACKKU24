"""
Test script for Alpha Vantage Market News & Sentiment API
Tests the news endpoint to verify API key and response format
"""

import requests
import json
from datetime import datetime
from config import Config

def test_market_news_api():
    """Test the Alpha Vantage News & Sentiment API endpoint"""
    
    print("="*70)
    print("Alpha Vantage Market News & Sentiment API Test")
    print("="*70)
    
    # Get API key from config
    api_key = Config.ALPHAVANTAGE_API_KEY
    
    if not api_key:
        print("ERROR: No API key found in config!")
        return
    
    print(f"\nAPI Key: {api_key[:12]}..." if len(api_key) > 12 else api_key)
    
    base_url = "https://www.alphavantage.co/query"
    
    # Test 1: Using topics (better for broad market coverage)
    print("\n" + "="*70)
    print("TEST 1: Using TOPICS for market news")
    print("="*70)
    
    topics_to_test = [
        'financial_markets',
        'technology'
    ]
    
    for topic in topics_to_test:
        print(f"\n{'─'*70}")
        print(f"Testing topic: {topic}")
        print(f"{'─'*70}")
        
        url = f"{base_url}?function=NEWS_SENTIMENT&topics={topic}&limit=50&apikey={api_key}"
        
        print(f"\nRequest URL: {url[:100]}...")
        
        try:
            print("\nSending request...")
            response = requests.get(url, timeout=30)
            
            print(f"Status Code: {response.status_code}")
            
            # Parse JSON response
            data = response.json()
            
            print(f"\nResponse Keys: {list(data.keys())}")
            
            # Check for errors or information messages
            if 'Information' in data:
                print(f"\n⚠️  API Information Message:")
                print(f"  {data['Information']}")
            
            if 'Note' in data:
                print(f"\n⚠️  API Note:")
                print(f"  {data['Note']}")
            
            # Check for feed data
            if 'feed' in data:
                feed = data['feed']
                print(f"\n✅ SUCCESS: Received {len(feed)} news items")
                
                if len(feed) > 0:
                    # Calculate simple average sentiment (no relevance weighting)
                    print(f"\n📊 Composite Sentiment Analysis (Simple Average):")
                    sentiment_scores = []
                    
                    for item in feed:
                        sentiment_score = item.get('overall_sentiment_score', 0)
                        sentiment_scores.append(sentiment_score)
                    
                    if sentiment_scores:
                        # Simple average to preserve Alpha Vantage thresholds
                        composite_score = sum(sentiment_scores) / len(sentiment_scores)
                        
                        # Determine label
                        if composite_score <= -0.35:
                            label = 'Bearish'
                        elif composite_score <= -0.15:
                            label = 'Somewhat-Bearish'
                        elif composite_score < 0.15:
                            label = 'Neutral'
                        elif composite_score < 0.35:
                            label = 'Somewhat-Bullish'
                        else:
                            label = 'Bullish'
                        
                        print(f"  Composite Score: {composite_score:.4f}")
                        print(f"  Composite Label: {label}")
                        print(f"  Articles Analyzed: {len(sentiment_scores)}")
                    
                    print(f"\nFirst news item sample:")
                    first_item = feed[0]
                    print(f"  Title: {first_item.get('title', 'N/A')[:80]}...")
                    print(f"  Source: {first_item.get('source', 'N/A')}")
                    print(f"  Overall Sentiment: {first_item.get('overall_sentiment_label', 'N/A')}")
                    print(f"  Sentiment Score: {first_item.get('overall_sentiment_score', 0)}")
            else:
                print(f"\n❌ NO FEED DATA in response")
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        # Brief pause between requests
        import time
        time.sleep(2)
    
    # Test 2: Bitcoin sentiment
    print("\n" + "="*70)
    print("TEST 2: Bitcoin (CRYPTO:BTC) Sentiment")
    print("="*70)
    
    ticker = 'CRYPTO:BTC'
    print(f"\n{'─'*70}")
    print(f"Testing ticker: {ticker}")
    print(f"{'─'*70}")
    
    url = f"{base_url}?function=NEWS_SENTIMENT&tickers={ticker}&limit=50&apikey={api_key}"
    
    print(f"\nRequest URL: {url[:100]}...")
    
    try:
        print("\nSending request...")
        response = requests.get(url, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        # Parse JSON response
        data = response.json()
        
        print(f"\nResponse Keys: {list(data.keys())}")
        
        # Check for errors or information messages
        if 'Information' in data:
            print(f"\n⚠️  API Information Message:")
            print(f"  {data['Information']}")
        
        if 'Note' in data:
            print(f"\n⚠️  API Note:")
            print(f"  {data['Note']}")
        
        if 'Error Message' in data:
            print(f"\n❌ API Error:")
            print(f"  {data['Error Message']}")
        
        # Check for feed data
        if 'feed' in data:
            feed = data['feed']
            print(f"\n✅ SUCCESS: Received {len(feed)} news items")
            
            if len(feed) > 0:
                # Calculate simple average sentiment (no relevance weighting)
                print(f"\n📊 Overall Sentiment for Bitcoin:")
                sentiment_scores = []
                
                for item in feed:
                    sentiment_score = item.get('overall_sentiment_score', 0)
                    sentiment_scores.append(sentiment_score)
                
                if sentiment_scores:
                    # Simple average to preserve Alpha Vantage thresholds
                    composite_score = sum(sentiment_scores) / len(sentiment_scores)
                    
                    # Determine label
                    if composite_score <= -0.35:
                        label = 'Bearish'
                    elif composite_score <= -0.15:
                        label = 'Somewhat-Bearish'
                    elif composite_score < 0.15:
                        label = 'Neutral'
                    elif composite_score < 0.35:
                        label = 'Somewhat-Bullish'
                    else:
                        label = 'Bullish'
                    
                    print(f"  Composite Score: {composite_score:.4f}")
                    print(f"  Composite Label: {label}")
                    print(f"  Articles Analyzed: {len(sentiment_scores)}")
                    
                
                print(f"\nFirst news item sample:")
                first_item = feed[0]
                print(f"  Title: {first_item.get('title', 'N/A')[:80]}...")
                print(f"  Source: {first_item.get('source', 'N/A')}")
                print(f"  Published: {first_item.get('time_published', 'N/A')}")
                print(f"  Overall Sentiment: {first_item.get('overall_sentiment_label', 'N/A')}")
                print(f"  Sentiment Score: {first_item.get('overall_sentiment_score', 0)}")
                
                # Show ticker sentiments if available
                if 'ticker_sentiment' in first_item and first_item['ticker_sentiment']:
                    print(f"  Ticker Sentiments: {len(first_item['ticker_sentiment'])} ticker(s)")
                    for ts in first_item['ticker_sentiment'][:5]:
                        print(f"    - {ts.get('ticker', 'N/A')}: {ts.get('ticker_sentiment_label', 'N/A')} (score: {ts.get('ticker_sentiment_score', 'N/A')})")
        else:
            print(f"\n❌ NO FEED DATA in response")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("Test completed")
    print(f"{'='*70}")


if __name__ == '__main__':
    test_market_news_api()
