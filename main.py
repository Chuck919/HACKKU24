import sqlite3

def read_from_database():
    # Connect to the SQLite database
    conn = sqlite3.connect('instance/users.db')
    
    # Create a cursor object to execute SQL queries
    cursor = conn.cursor()
    
    # Execute a SQL query to select all rows from the 'users' table
    cursor.execute('SELECT * FROM user')
    
    # Fetch all rows from the cursor
    rows = cursor.fetchall()
    
    # Iterate over the rows and print each row
    for row in rows:
        print(row)
    
    # Close the cursor and connection
    cursor.close()
    conn.close()

# Call the function to read from the database
read_from_database()