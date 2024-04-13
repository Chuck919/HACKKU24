import sqlite3

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
            user_info[email] = text
        
        # Close the cursor and connection
        cursor.close()
        conn.close()

        return user_info
    except Exception as e:
        print("Error reading from database:", e)

if __name__ == '__main__':
    user_info = read_from_database()
    print("User info from database:", user_info)