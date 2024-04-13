
import http.client
import urllib.parse
from datetime import datetime

def date():
    current_date = datetime.now().date()

    formatted_date = current_date.strftime('%Y-%m-%d')

    return str(formatted_date)

def fetch_news(keyword):

    conn = http.client.HTTPConnection('api.mediastack.com')

    today = date()
    print(today)
    params = urllib.parse.urlencode({
        'access_key': '***REMOVED***', #You will need your own access key
        'countries': 'us',
        'languages': 'en',
        'keywords': keyword,
        'date': today,
        'sort': 'published_asc',
        'limit': 100,
        })


    conn.request('GET', '/v1/news?{}'.format(params))

    res = conn.getresponse()
    data = res.read()

    print(data.decode('utf-8'))
    
fetch_news('Bitcoin')