from flask import Flask, render_template
from flask_mail import Mail, Message
import sqlite3
import http.client
import urllib.parse
from datetime import datetime, timedelta
import json
from config import Config
import yfinance as yf
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
import pandas as pd
import numpy as np
import io
import base64
import os
import time
import requests

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Mail
mail = Mail(app)

# Top 10 S&P 500 stocks by percentage weight (as of 2025)
# Sorted by actual S&P 500 index weight, not market cap
TOP_10_SP500 = ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'AVGO', 'GOOG', 'META',  'TSLA', 'BRK.B']

def fetch_insider_transactions(symbols_list):
    """
    Fetch insider transactions for multiple symbols using batch approach
    Returns dict with symbol as key and list of transactions as value
    """
    print(f"  Fetching insider transactions for {len(symbols_list)} companies...")
    
    if not app.config.get('ALPHAVANTAGE_API_KEY'):
        print("    WARNING: No Alpha Vantage API key configured")
        return {}
    
    insider_data = {}
    api_key = app.config['ALPHAVANTAGE_API_KEY']
    
    # Limit to first 5 symbols to avoid rate limiting (5 calls per minute limit)
    for symbol in symbols_list[:5]:
        try:
            params = {
                'function': 'INSIDER_TRANSACTIONS',
                'symbol': symbol,
                'apikey': api_key
            }
            
            response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
            data = response.json()
            
            if 'data' in data and len(data['data']) > 0:
                # Get most recent 3 transactions
                transactions = []
                for tx in data['data'][:3]:
                    transactions.append({
                        'name': tx.get('name', 'Unknown'),
                        'shares': tx.get('acquisition_or_disposition', 'N/A'),
                        'shares_traded': tx.get('securities_transacted', '0'),
                        'price': tx.get('securities_owned', 'N/A'),
                        'date': tx.get('transaction_date', 'N/A')
                    })
                
                insider_data[symbol] = transactions
                print(f"    SUCCESS: {symbol}: {len(transactions)} transactions")
            
        except Exception as e:
            print(f"    ✗ {symbol} failed: {str(e)[:50]}")
            continue
    
    return insider_data

def fetch_market_news_sentiment(topics=None, tickers=None, limit=10):
    """
    Fetch market news with sentiment analysis
    Uses condensed API call to get news for multiple tickers/topics
    """
    print(f"  Fetching market news & sentiment...")
    
    if not app.config.get('ALPHAVANTAGE_API_KEY'):
        print("    WARNING: No Alpha Vantage API key configured")
        return []
    
    try:
        params = {
            'function': 'NEWS_SENTIMENT',
            'apikey': app.config['ALPHAVANTAGE_API_KEY'],
            'sort': 'LATEST',
            'limit': limit
        }
        
        # Add tickers if provided (comma-separated for batch request)
        if tickers:
            params['tickers'] = ','.join(tickers[:10])  # Limit to 10 tickers
        
        # Add topics if provided
        if topics:
            params['topics'] = ','.join(topics)
        
        response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
        data = response.json()
        
        if 'feed' in data:
            news_items = []
            for item in data['feed'][:limit]:
                # Get ticker sentiments
                ticker_sentiments = {}
                if 'ticker_sentiment' in item:
                    for ts in item['ticker_sentiment'][:3]:  # Top 3 tickers mentioned
                        ticker_sentiments[ts.get('ticker', 'N/A')] = {
                            'relevance': float(ts.get('relevance_score', 0)),
                            'sentiment': ts.get('ticker_sentiment_label', 'Neutral')
                        }
                
                news_items.append({
                    'title': item.get('title', 'No title'),
                    'url': item.get('url', '#'),
                    'time_published': item.get('time_published', 'N/A'),
                    'source': item.get('source', 'Unknown'),
                    'summary': item.get('summary', 'No summary')[:200] + '...',
                    'overall_sentiment': item.get('overall_sentiment_label', 'Neutral'),
                    'sentiment_score': float(item.get('overall_sentiment_score', 0)),
                    'ticker_sentiments': ticker_sentiments
                })
            
            print(f"    SUCCESS: Retrieved {len(news_items)} news articles")
            return news_items
        
        return []
        
    except Exception as e:
        print(f"    ✗ News fetch failed: {str(e)[:100]}")
        return []

def fetch_alphavantage_data(symbol, api_key):
    """
    Fetch stock data from Alpha Vantage API
    Returns dict with OHLC data or None if failed
    """
    try:
        # Map common symbols to Alpha Vantage format
        symbol_map = {
            '^GSPC': 'SPY',      # S&P 500 ETF as proxy
            '^IXIC': 'QQQ',      # NASDAQ 100 ETF as proxy
            'BTC-USD': 'BTC'     # Bitcoin
        }
        
        av_symbol = symbol_map.get(symbol, symbol)
        
        # Determine function based on asset type
        if av_symbol == 'BTC':
            function = 'DIGITAL_CURRENCY_DAILY'
            params = {
                'function': function,
                'symbol': 'BTC',
                'market': 'USD',
                'apikey': api_key
            }
        else:
            function = 'TIME_SERIES_DAILY'
            params = {
                'function': function,
                'symbol': av_symbol,
                'outputsize': 'compact',  # Last 100 days
                'apikey': api_key
            }
        
        # Build request using requests library
        response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
        data = response.json()
        
        # Parse response based on function type
        if av_symbol == 'BTC':
            time_series_key = 'Time Series (Digital Currency Daily)'
            open_key = '1. open'
            high_key = '2. high'
            low_key = '3. low'
            close_key = '4. close'
        else:
            time_series_key = 'Time Series (Daily)'
            open_key = '1. open'
            high_key = '2. high'
            low_key = '3. low'
            close_key = '4. close'
        
        if time_series_key not in data:
            return None
        
        time_series = data[time_series_key]
        
        # Convert to OHLC dict
        ohlc_data = {
            'dates': [],
            'open': [],
            'high': [],
            'low': [],
            'close': []
        }
        
        for date, values in sorted(time_series.items())[:30]:  # Last 30 days
            ohlc_data['dates'].append(date)
            ohlc_data['open'].append(float(values[open_key]))
            ohlc_data['high'].append(float(values[high_key]))
            ohlc_data['low'].append(float(values[low_key]))
            ohlc_data['close'].append(float(values[close_key]))
        
        if len(ohlc_data['close']) >= 5:
            return ohlc_data
        
        return None
        
    except Exception as e:
        print(f"    Alpha Vantage error: {str(e)[:100]}")
        return None

def generate_market_charts(user_prefs=None):
    """
    Generate candlestick charts for requested markets
    user_prefs: dict with keys like 'sp500', 'nasdaq', 'bitcoin'
    Returns a dictionary with base64 encoded images
    """
    if user_prefs is None:
        user_prefs = {'sp500': True, 'nasdaq': True, 'bitcoin': True}
    
    charts = {}
    
    # Define the tickers based on user preferences
    tickers = {}
    if user_prefs.get('sp500', False):
        tickers['S&P 500'] = '^GSPC'
    if user_prefs.get('nasdaq', False):
        tickers['NASDAQ'] = '^IXIC'
    if user_prefs.get('bitcoin', False):
        tickers['Bitcoin'] = 'BTC-USD'
    
    if not tickers:
        return charts
    
    # Try to get real data first
    print(f"  Attempting to fetch market data for {len(tickers)} charts...")
    
    for name, ticker in tickers.items():
        try:
            print(f"  Generating candlestick chart for {name}...")
            
            # Multi-layer fallback: Alpha Vantage → Yahoo Finance → Mock Data
            ohlc_data = None
            data_source = "unknown"
            
            # Layer 1: Try Alpha Vantage first (more reliable for free tier)
            if app.config.get('ALPHAVANTAGE_API_KEY'):
                try:
                    print(f"    Trying Alpha Vantage...")
                    ohlc_data = fetch_alphavantage_data(ticker, app.config['ALPHAVANTAGE_API_KEY'])
                    if ohlc_data and len(ohlc_data['close']) >= 5:
                        data_source = "Alpha Vantage"
                        print(f"    SUCCESS: Alpha Vantage: {len(ohlc_data['close'])} candles")
                except Exception as e:
                    print(f"    ERROR: Alpha Vantage failed: {str(e)[:50]}")
            
            # Layer 2: Try Yahoo Finance if Alpha Vantage failed
            if ohlc_data is None:
                try:
                    print(f"    Trying Yahoo Finance...")
                    ticker_obj = yf.Ticker(ticker)
                    data = ticker_obj.history(period='1mo', interval='1d')
                    if not data.empty and len(data) >= 5:
                        ohlc_data = {
                            'dates': [str(d.date()) for d in data.index],
                            'open': data['Open'].values,
                            'high': data['High'].values,
                            'low': data['Low'].values,
                            'close': data['Close'].values
                        }
                        data_source = "Yahoo Finance"
                        print(f"    SUCCESS: Yahoo Finance: {len(ohlc_data['close'])} candles")
                except Exception as e:
                    print(f"    ERROR: Yahoo Finance failed: {str(e)[:50]}")
            
            # Layer 3: Use mock data as final fallback
            if ohlc_data is None or len(ohlc_data['close']) < 5:
                print(f"    Using mock data (all APIs unavailable)")
                ohlc_data = generate_mock_ohlc_data(name, 30)
                data_source = "Mock Data"
            
            # Create candlestick chart
            chart_img = create_candlestick_chart(name, ohlc_data, data_source)
            if chart_img:
                charts[name] = chart_img
                print(f"  SUCCESS: Chart generated for {name}")
            
        except Exception as e:
            print(f"  ERROR: Error generating chart for {name}: {str(e)[:100]}")
            continue
    
    return charts

def create_candlestick_chart(name, ohlc_data, data_source):
    """Create a candlestick chart from OHLC data"""
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        opens = np.array(ohlc_data['open'])
        highs = np.array(ohlc_data['high'])
        lows = np.array(ohlc_data['low'])
        closes = np.array(ohlc_data['close'])
        
        # Calculate percentage change
        pct_change = ((closes[-1] - closes[0]) / closes[0]) * 100
        change_text = f"{'+' if pct_change >= 0 else ''}{pct_change:.2f}%"
        change_color = 'green' if pct_change >= 0 else 'red'
        
        # Plot candlesticks
        for i in range(len(opens)):
            # Determine color
            if closes[i] >= opens[i]:
                color = '#26a69a'  # Green for up
                body_color = color
                edge_color = color
            else:
                color = '#ef5350'  # Red for down
                body_color = color
                edge_color = color
            
            # Draw high-low line
            ax.plot([i, i], [lows[i], highs[i]], color=edge_color, linewidth=1, solid_capstyle='round')
            
            # Draw open-close body
            body_height = abs(closes[i] - opens[i])
            body_bottom = min(opens[i], closes[i])
            
            rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                           facecolor=body_color, edgecolor=edge_color, linewidth=1.5)
            ax.add_patch(rect)
        
        # Set proper y-axis limits with padding
        y_min = min(lows) * 0.995
        y_max = max(highs) * 1.005
        ax.set_ylim(y_min, y_max)
        
        # Formatting
        ax.set_title(f'{name} - Last 30 Days ({change_text}) [{data_source}]', 
                    fontsize=14, fontweight='bold', color=change_color)
        ax.set_xlabel('Days', fontsize=10)
        ax.set_ylabel('Price (USD)', fontsize=10)
        ax.grid(True, alpha=0.2, linestyle='--', axis='y')
        ax.set_xlim(-1, len(opens))
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Adjust layout
        plt.tight_layout()
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        # Encode to base64
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        # Close the plot
        plt.close(fig)
        buf.close()
        
        return img_base64
        
    except Exception as e:
        print(f"  Error creating candlestick chart: {str(e)}")
        return None

def generate_mock_ohlc_data(asset_name, num_days=30):
    """Generate realistic mock OHLC data"""
    # Base prices for different assets
    base_prices = {
        'S&P 500': 4500.0,
        'NASDAQ': 15000.0,
        'Bitcoin': 35000.0
    }
    
    base_price = base_prices.get(asset_name, 1000.0)
    
    # Generate random walk
    np.random.seed(hash(asset_name) % (2**32))
    
    ohlc_data = {
        'dates': [],
        'open': [],
        'high': [],
        'low': [],
        'close': []
    }
    
    current_price = base_price
    for i in range(num_days):
        open_price = current_price
        
        # Daily change
        daily_change = np.random.normal(0.001, 0.02)
        close_price = float(open_price * (1 + daily_change))
        
        # High and low
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
        
        ohlc_data['dates'].append(f'Day {i+1}')
        ohlc_data['open'].append(float(open_price))
        ohlc_data['high'].append(float(high_price))
        ohlc_data['low'].append(float(low_price))
        ohlc_data['close'].append(float(close_price))
        
        current_price = close_price
    
    return ohlc_data

def generate_mock_price_data(asset_name, num_days=90):
    """
    Generate realistic mock price data for demonstration when API is unavailable
    """
    import numpy as np
    
    # Base prices for different assets
    base_prices = {
        'S&P 500': 4500.0,
        'NASDAQ': 15000.0,
        'Bitcoin': 35000.0
    }
    
    base_price = base_prices.get(asset_name, 1000.0)
    
    # Generate random walk with slight upward trend
    np.random.seed(hash(asset_name) % (2**32))  # Consistent data for same asset
    
    prices = [base_price]
    for i in range(num_days - 1):
        # Random daily change between -2% and +2.5% (slight bull bias)
        change_pct = np.random.normal(0.001, 0.015)
        new_price = float(prices[-1] * (1 + change_pct))
        prices.append(new_price)
    
    return np.array(prices)

def fetch_top10_sp500_stocks():
    """
    Fetch top 10 S&P 500 stocks with current price and daily change
    Uses Alpha Vantage API for each ticker
    NOTE: Alpha Vantage has a rate limit of 5 calls/minute
    This function will take ~5 minutes to complete all 10 stocks
    """
    print("  Fetching Top 10 S&P 500 stocks...")
    print("  NOTE: Rate limit is 5 calls/minute, this will take ~5 minutes")
    
    if not app.config.get('ALPHAVANTAGE_API_KEY'):
        print("    WARNING: No Alpha Vantage API key configured, using mock data")
        return generate_mock_top10_data()
    
    stocks_data = []
    api_key = app.config['ALPHAVANTAGE_API_KEY']
    
    for idx, symbol in enumerate(TOP_10_SP500, 1):
        try:
            # Fetch data from Alpha Vantage using requests library (more reliable on PythonAnywhere)
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Check for rate limit message
            if 'Note' in data or 'Information' in data:
                print(f"    WARNING: {symbol}: API rate limit reached")
                print(f"    Message: {data.get('Note') or data.get('Information')}")
                # Wait and retry once
                print(f"    Waiting 60 seconds to respect rate limit...")
                time.sleep(60)
                continue
            
            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                current_price = float(quote.get('05. price', 0))
                previous_close = float(quote.get('08. previous close', 0))
                
                if current_price > 0 and previous_close > 0:
                    daily_change = current_price - previous_close
                    daily_change_pct = (daily_change / previous_close) * 100
                    
                    stocks_data.append({
                        'symbol': symbol,
                        'price': current_price,
                        'change': daily_change,
                        'change_pct': daily_change_pct,
                        'direction': 'up' if daily_change >= 0 else 'down'
                    })
                    print(f"    SUCCESS: {symbol}: ${current_price:.2f} ({daily_change_pct:+.2f}%)")
                else:
                    print(f"    WARNING: {symbol}: Invalid price data")
            else:
                print(f"    WARNING: {symbol}: No data returned from API")
            
            # Rate limiting: 5 calls per minute = wait 30 seconds between calls for safety
            if idx < len(TOP_10_SP500):
                wait_time = 30
                print(f"    [{idx}/{len(TOP_10_SP500)}] Waiting {wait_time}s for rate limit...")
                time.sleep(wait_time)
                
        except requests.exceptions.RequestException as e:
            print(f"    ERROR: {symbol} request failed: {str(e)[:100]}")
            continue
        except Exception as e:
            print(f"    ERROR: {symbol} failed: {str(e)[:50]}")
            continue
    
    if len(stocks_data) >= 5:
        print(f"  SUCCESS: Successfully fetched {len(stocks_data)}/10 stocks")
        return stocks_data
    else:
        print(f"  WARNING: Not enough data ({len(stocks_data)}/10), using mock data")
        return generate_mock_top10_data()


def generate_mock_top10_data():
    """Generate mock data for top 10 stocks"""
    stocks_data = []
    base_prices = {
        'AAPL': 175.0, 'MSFT': 380.0, 'NVDA': 500.0, 'AMZN': 145.0,
        'META': 330.0, 'GOOGL': 140.0, 'TSLA': 245.0, 'BRK.B': 360.0,
        'LLY': 750.0, 'AVGO': 170.0
    }
    
    np.random.seed(42)
    for symbol in TOP_10_SP500:
        base_price = base_prices[symbol]
        daily_change_pct = np.random.normal(0, 1.5)
        daily_change = base_price * (daily_change_pct / 100)
        
        stocks_data.append({
            'symbol': symbol,
            'price': base_price,
            'change': daily_change,
            'change_pct': daily_change_pct,
            'direction': 'up' if daily_change >= 0 else 'down'
        })
    
    return stocks_data

def send_email(email, articles, charts=None, top10_stocks=None, insider_data=None, market_news=None):
    try:
        print(f"\n{'='*60}")
        print(f"EMAIL SEND DEBUG for {email}")
        print(f"{'='*60}")
        
        # Check Flask-Mail configuration
        print(f"  Mail Configuration:")
        print(f"    MAIL_SERVER: {app.config.get('MAIL_SERVER', 'NOT SET')}")
        print(f"    MAIL_PORT: {app.config.get('MAIL_PORT', 'NOT SET')}")
        print(f"    MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'NOT SET')}")
        print(f"    MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'NOT SET')}")
        print(f"    MAIL_PASSWORD: {'SET' if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
        
        # Check content
        print(f"\n  Email Content:")
        print(f"    Recipient: {email}")
        print(f"    Articles: {len(articles)} keyword(s), {sum(len(v) for v in articles.values())} total articles")
        print(f"    Charts: {len(charts) if charts else 0}")
        print(f"    Top 10 Stocks: {len(top10_stocks) if top10_stocks else 0}")
        print(f"    Insider Data: {len(insider_data) if insider_data else 0} symbols")
        print(f"    Market News: {len(market_news) if market_news else 0} items")
        
        msg = Message('AnyNews Daily Update',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email])
        
        print(f"\n  Rendering email template...")
        email_body = render_template('daily_mail.html', articles=articles, charts=charts, 
                                     top10_stocks=top10_stocks, insider_data=insider_data, 
                                     market_news=market_news)
        print(f"    Template rendered successfully (size: {len(email_body)} chars)")
        msg.html = email_body

        print(f"\n  Attempting to send via SMTP...")
        mail.send(msg)
        print(f"  SUCCESS: Email sent successfully to {email}")
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"\n  ERROR DETAILS:")
        print(f"    Error Type: {type(e).__name__}")
        print(f"    Error Message: {str(e)}")
        import traceback
        print(f"    Full Traceback:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        raise

def read_from_database():
    try:
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user')
        rows = cursor.fetchall()
        user_info = []
        for row in rows:
            user_info.append({
                'email': row[1],
                'text': row[2],
                'token': row[3],
                'include_charts': bool(row[4]) if len(row) > 4 else False,
                'include_sp500_chart': bool(row[5]) if len(row) > 5 else False,
                'include_nasdaq_chart': bool(row[6]) if len(row) > 6 else False,
                'include_bitcoin_chart': bool(row[7]) if len(row) > 7 else False,
                'include_top10_stocks': bool(row[8]) if len(row) > 8 else False,
                'include_stock_suite': bool(row[9]) if len(row) > 9 else False,
                'include_market_news': bool(row[10]) if len(row) > 10 else False
            })
        cursor.close()
        conn.close()
        return user_info
    except Exception as e:
        print("Error reading from database:", e)
        return []

def date():
    current_date = datetime.now().date()
    formatted_date = current_date.strftime('%Y-%m-%d')
    return str(formatted_date)

def fetch_news(keyword):
    conn = None
    try:
        conn = http.client.HTTPConnection('api.mediastack.com', timeout=10)
        today = date()
        params = urllib.parse.urlencode({
            'access_key': app.config['MEDIASTACK_API_KEY'],
            'countries': 'us',
            'languages': 'en',
            'keywords': keyword,
            'date': today,
            'sort': 'published_desc',
            'limit': 3,
        })
        
        print(f"Fetching news for keyword: {keyword}")
        conn.request('GET', '/v1/news?{}'.format(params))
        res = conn.getresponse()
        data = res.read()
        articles = json.loads(data.decode('utf-8'))
        
        # Check for API errors
        if 'error' in articles:
            print(f"API Error: {articles['error']}")
            return []
        
        return articles.get('data', [])
    except Exception as e:
        print(f"Error fetching news for keyword '{keyword}': {e}")
        return []
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("=" * 50)
    print("Starting AnyNews Daily Email Service")
    print("=" * 50)
    
    # Debug configuration
    print("\nSystem Configuration Check:")
    
    # Check if .env file exists
    import os
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"  .env file exists: {os.path.exists(env_path)}")
    if os.path.exists(env_path):
        print(f"  .env file path: {env_path}")
    
    print(f"  Python App Context: {'Active' if app.app_context else 'Inactive'}")
    print(f"  Database Path: instance/users.db")
    print(f"  MAIL_SERVER: {app.config.get('MAIL_SERVER', 'NOT CONFIGURED')}")
    print(f"  MAIL_PORT: {app.config.get('MAIL_PORT', 'NOT CONFIGURED')}")
    print(f"  MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'NOT CONFIGURED')}")
    print(f"  MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'NOT CONFIGURED')}")
    print(f"  MAIL_PASSWORD: {'Configured (' + str(len(app.config.get('MAIL_PASSWORD', ''))) + ' chars)' if app.config.get('MAIL_PASSWORD') else 'NOT CONFIGURED'}")
    print(f"  MEDIASTACK_API_KEY: {'Configured' if app.config.get('MEDIASTACK_API_KEY') else 'NOT CONFIGURED'}")
    print(f"  ALPHAVANTAGE_API_KEY: {'Configured' if app.config.get('ALPHAVANTAGE_API_KEY') else 'NOT CONFIGURED'}")
    
    with app.app_context():
        user_info = read_from_database()
        print(f"\nFound {len(user_info) if user_info else 0} users in database")
        
        if user_info:
            for idx, user in enumerate(user_info, 1):
                email = user['email']
                keywords_text = user['text'].strip()
                include_charts = user.get('include_charts', False)
                include_sp500 = user.get('include_sp500_chart', False)
                include_nasdaq = user.get('include_nasdaq_chart', False)
                include_bitcoin = user.get('include_bitcoin_chart', False)
                include_top10 = user.get('include_top10_stocks', False)
                include_stock_suite = user.get('include_stock_suite', False)
                include_news_sentiment = user.get('include_market_news', False) if not include_stock_suite else True
                
                print(f"\n[{idx}/{len(user_info)}] Processing user: {email}")
                print(f"  Charts: SP500={include_sp500}, NASDAQ={include_nasdaq}, Bitcoin={include_bitcoin}")
                print(f"  Top 10 Stocks: {'Yes' if include_top10 else 'No'}")
                print(f"  Stock Suite: {'Yes' if include_stock_suite else 'No'}")
                print(f"  Market News: {'Yes' if include_news_sentiment else 'No'}")
                
                # Fetch keyword-based news articles
                articles_by_keyword = {}
                if keywords_text and not keywords_text.isspace():
                    keywords = [keyword.strip() for keyword in keywords_text.split(',') if keyword.strip()]
                    print(f"  Keywords: {', '.join(keywords)}")

                    for keyword in keywords:
                        articles = fetch_news(keyword)
                        print(f"  → Found {len(articles)} articles for '{keyword}'")
                        
                        articles_for_user = []
                        for article in articles:
                            try:
                                article_info = {
                                    'title': article.get('title', 'No title'),
                                    'description': article.get('description', 'No description'),
                                    'source': article.get('source', 'Unknown'),
                                    'link': article.get('url', '#')
                                }
                                articles_for_user.append(article_info)
                            except Exception as e:
                                print(f"  ERROR: Error processing article: {e}")
                        
                        if articles_for_user:
                            articles_by_keyword[keyword] = articles_for_user
                else:
                    print(f"  No keywords provided")
                
                # Check if user has ANY content to send (keywords OR stock features)
                has_stock_features = (include_sp500 or include_nasdaq or include_bitcoin or 
                                     include_top10 or include_news_sentiment)
                has_content = bool(articles_by_keyword) or has_stock_features
                
                if has_content:
                    total_articles = sum(len(arts) for arts in articles_by_keyword.values()) if articles_by_keyword else 0
                    print(f"  Preparing email with {total_articles} total articles...")
                    
                    # Generate charts only if user wants them
                    user_charts = {}
                    if include_sp500 or include_nasdaq or include_bitcoin:
                        user_prefs = {
                            'sp500': include_sp500,
                            'nasdaq': include_nasdaq,
                            'bitcoin': include_bitcoin
                        }
                        user_charts = generate_market_charts(user_prefs)
                    
                    # Get top 10 stocks if user wants them
                    user_top10 = fetch_top10_sp500_stocks() if include_top10 else None
                    
                    # Get market news sentiment if user wants it
                    user_market_news = None
                    if include_news_sentiment:
                        # Track S&P 500, NASDAQ, and Bitcoin
                        user_market_news = fetch_market_news_sentiment(
                            topics=['financial_markets', 'economy_macro', 'blockchain'],
                            tickers=['SPY', 'QQQ', 'BTC'],  # S&P 500, NASDAQ, and Bitcoin
                            limit=10
                        )
                    
                    print(f"  Attempting to send email to {email}...")
                    print(f"    Articles: {len(articles_by_keyword)} keyword(s)")
                    print(f"    Charts: {len(user_charts)} chart(s)")
                    print(f"    Top 10 stocks: {'Yes' if user_top10 else 'No'}")
                    print(f"    Market news: {'Yes' if user_market_news else 'No'}")
                    
                    send_email(email, articles_by_keyword, user_charts, user_top10, None, user_market_news)
                else:
                    print(f"  WARNING: No content to send (no keywords and no stock features enabled)")
        else:
            print("\nWARNING: No users found in database")
    
    print("\n" + "=" * 50)
    print("Email service completed!")
    print("=" * 50)