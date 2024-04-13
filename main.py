from flask import Flask, render_template
from flask_mail import Mail, Message
import sqlite3
import http.client
import urllib.parse
from datetime import datetime
import json

app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = '***REMOVED***'
app.config['MAIL_PASSWORD'] = '***REMOVED***'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# Initialize Flask-Mail
mail = Mail(app)

def send_email(email, keyword, articles):
    
    msg = Message('News Update: {}'.format(keyword),
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[email])

    email_body = render_template('daily_mail.html', keyword=keyword, articles=articles)
    msg.html = email_body

    mail.send(msg)

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
                'token': row[3]
            })
        cursor.close()
        conn.close()
        return user_info
    except Exception as e:
        print("Error reading from database:", e)

def date():
    current_date = datetime.now().date()
    formatted_date = current_date.strftime('%Y-%m-%d')
    return str(formatted_date)

def fetch_news(keyword):
    conn = http.client.HTTPConnection('api.mediastack.com')
    today = date()
    params = urllib.parse.urlencode({
        'access_key': '***REMOVED***',
        'countries': 'us',
        'languages': 'en',
        'keywords': keyword,
        'date': today,
        'sort': 'published_asc',
        'limit': 3,
    })
    conn.request('GET', '/v1/news?{}'.format(params))
    res = conn.getresponse()
    data = res.read()
    articles = json.loads(data.decode('utf-8'))
    return articles.get('data', [])

if __name__ == '__main__':
    with app.app_context():
        user_info = read_from_database()
        print("User info from database:", user_info)
        
        if user_info:
            for user in user_info:
                email = user['email']
                keywords_text = user['text'].strip()  # Remove leading and trailing white spaces
                
                if keywords_text:
                    keywords = [keyword.strip() for keyword in keywords_text.split(',')]  # Split by comma and remove white spaces
                    
                    articles_for_user = []
                    for keyword in keywords:
                        articles = fetch_news(keyword)
                        print(f"Fetching news for user with email: {email} and keyword: {keyword}")
                        print("Number of articles fetched:", len(articles))
                        
                        articles_for_user.extend(articles)
                        
                    if articles_for_user:
                        send_email(email, keywords, articles_for_user)
                    else:
                        print(f"No articles found for user with email: {email}")
                else:
                    print(f"No keywords found for user with email: {email}")