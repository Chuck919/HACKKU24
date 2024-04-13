from flask import Flask, render_template
from flask_mail import Mail, Message
import sqlite3
import http.client
import urllib.parse
from datetime import datetime
import json

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
        
        
print(read_from_database())