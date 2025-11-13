"""
Database migration script to add include_charts column to existing database
Run this once to update your database schema
"""
import sqlite3

def migrate_database():
    try:
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'include_charts' not in columns:
            print("Adding 'include_charts' column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN include_charts BOOLEAN DEFAULT 0 NOT NULL")
            conn.commit()
            print("✓ Migration completed successfully!")
        else:
            print("✓ Column 'include_charts' already exists. No migration needed.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ Error during migration: {e}")

if __name__ == '__main__':
    print("=" * 50)
    print("Database Migration Script")
    print("=" * 50)
    migrate_database()
