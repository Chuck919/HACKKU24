"""
Database Migration Script: Remove include_insider_trading Column
This script removes the include_insider_trading column from the user table.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = 'instance/users.db'

def backup_database():
    """Create a backup of the database before migration"""
    if os.path.exists(DB_PATH):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'instance/users_backup_{timestamp}.db'
        
        # Copy database
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"SUCCESS: Database backed up to {backup_path}")
        return backup_path
    else:
        print(f"WARNING: Database not found at {DB_PATH}")
        return None

def remove_insider_column():
    """Remove the include_insider_trading column from the user table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"\nCurrent columns: {column_names}")
        
        if 'include_insider_trading' not in column_names:
            print("INFO: Column 'include_insider_trading' does not exist. No migration needed.")
            cursor.close()
            conn.close()
            return
        
        print("\nRemoving 'include_insider_trading' column...")
        
        # SQLite doesn't support DROP COLUMN directly (in older versions)
        # We need to recreate the table without the column
        
        # Get all data from current table
        cursor.execute("SELECT * FROM user")
        all_users = cursor.fetchall()
        
        # Create new table without include_insider_trading column
        cursor.execute("""
            CREATE TABLE user_new (
                id INTEGER PRIMARY KEY,
                email VARCHAR(120) UNIQUE NOT NULL,
                text TEXT NOT NULL,
                unsubscribe_token VARCHAR(32) UNIQUE NOT NULL,
                include_charts BOOLEAN NOT NULL,
                include_sp500_chart BOOLEAN NOT NULL,
                include_nasdaq_chart BOOLEAN NOT NULL,
                include_bitcoin_chart BOOLEAN NOT NULL,
                include_top10_stocks BOOLEAN NOT NULL,
                include_stock_suite BOOLEAN NOT NULL,
                include_market_news BOOLEAN NOT NULL
            )
        """)
        
        # Insert data into new table (excluding include_insider_trading column)
        # Old schema: id, email, text, token, charts, sp500, nasdaq, bitcoin, top10, suite, insider, news
        # New schema: id, email, text, token, charts, sp500, nasdaq, bitcoin, top10, suite, news
        for row in all_users:
            cursor.execute("""
                INSERT INTO user_new 
                (id, email, text, unsubscribe_token, include_charts, include_sp500_chart, 
                 include_nasdaq_chart, include_bitcoin_chart, include_top10_stocks, 
                 include_stock_suite, include_market_news)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row[0],  # id
                row[1],  # email
                row[2],  # text
                row[3],  # unsubscribe_token
                row[4],  # include_charts
                row[5],  # include_sp500_chart
                row[6],  # include_nasdaq_chart
                row[7],  # include_bitcoin_chart
                row[8],  # include_top10_stocks
                row[9],  # include_stock_suite
                row[11]  # include_market_news (skip row[10] which is insider)
            ))
        
        # Drop old table and rename new table
        cursor.execute("DROP TABLE user")
        cursor.execute("ALTER TABLE user_new RENAME TO user")
        
        conn.commit()
        
        # Verify the new schema
        cursor.execute("PRAGMA table_info(user)")
        new_columns = cursor.fetchall()
        new_column_names = [col[1] for col in new_columns]
        
        print(f"\nNew columns: {new_column_names}")
        print(f"SUCCESS: Migrated {len(all_users)} users")
        print("SUCCESS: Column 'include_insider_trading' has been removed")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration: Remove include_insider_trading Column")
    print("=" * 60)
    
    # Create backup first
    backup_path = backup_database()
    
    if backup_path or not os.path.exists(DB_PATH):
        # Proceed with migration
        remove_insider_column()
    else:
        print("ERROR: Could not create backup. Aborting migration.")
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
