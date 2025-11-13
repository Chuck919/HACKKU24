"""
Database migration script to add new chart preference columns
Run this to update existing database schema
"""
import sqlite3

def migrate_database():
    print("Starting database migration...")
    
    try:
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()
        
        # Add new columns if they don't exist
        new_columns = [
            ('include_sp500_chart', 'BOOLEAN DEFAULT 0'),
            ('include_nasdaq_chart', 'BOOLEAN DEFAULT 0'),
            ('include_bitcoin_chart', 'BOOLEAN DEFAULT 0'),
            ('include_top10_stocks', 'BOOLEAN DEFAULT 0')
        ]
        
        for column_name, column_type in new_columns:
            try:
                cursor.execute(f'ALTER TABLE user ADD COLUMN {column_name} {column_type}')
                print(f"✓ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print(f"  Column {column_name} already exists, skipping")
                else:
                    raise
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Show current schema
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        print("\nCurrent user table schema:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    migrate_database()
