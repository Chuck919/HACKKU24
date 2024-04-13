import sqlite3
import http.client
import urllib.parse
import json

def read_from_database():
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('instance/users.db')
        
        # Create a cursor object to execute SQL queries
        cursor = conn.cursor()
        
        # Execute a SQL query to select all rows from the 'user' table
        cursor.execute('SELECT * FROM user')
        
        # Fetch all rows from the cursor
        rows = cursor.fetchall()
        
        # Create a dictionary to store user info
        user_info = {}
        for row in rows:
            email = row[1]  # Assuming email is in the second column
            text = row[2]   # Assuming text is in the third column
            user_info[email] = text.split(', ')  # Split text by commas to get individual strings
        
        # Close the cursor and connection
        cursor.close()
        conn.close()

        return user_info
    except Exception as e:
        print("Error reading from database:", e)

def fetch_news(keywords):
    conn = http.client.HTTPConnection('api.mediastack.com')

    print(keywords)
    
    params = urllib.parse.urlencode({
        'access_key': '***REMOVED***', #You will need your own access key
        'countries': 'us',
        'languages': 'en',
        'keywords': keywords,
        'sort': 'published_desc',
        'limit': 100,
        })


    conn.request('GET', '/v1/news?{}'.format(params))

    res = conn.getresponse()
    data = res.read().decode('utf-8')

    json_data = json.loads(data)

    articles = []
    for article in json_data.get('data', []):
        author = article.get('author', '')
        title = article.get('title', '')
        description = article.get('description', '')
        url = article.get('url', '')
        source = article.get('source', '')
        image = article.get('image', '')
        category = article.get('category', '')
        language = article.get('language', '')
        country = article.get('country', '')
        published_at = article.get('published_at', '')

        articles.append({
            'Author': author,
            'Title': title,
            'Description': description,
            'URL': url,
            'Source': source,
            'Image': image,
            'Category': category,
            'Language': language,
            'Country': country,
            'Published_at': published_at
        })

    return articles

if __name__ == '__main__':
    user_info = read_from_database()
    print("User info from database:", user_info)

    for email, text in user_info.items():
        print(f"Fetching news for user with email: {email} and text: {text}")
        articles = fetch_news(text)
        print("Number of articles fetched:", len(articles))
        print("Sample article:", articles[0] if articles else "No articles found")