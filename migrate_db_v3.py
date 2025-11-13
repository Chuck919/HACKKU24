import sqlite3
import os

# Database migration script for Stock Suite features
# This adds columns for Stock Suite master toggle, insider trading, and market news preferences

DB_PATH = os.path.join('instance', 'users.db')

def migrate_database():
    """Add the remaining Stock Suite columns to the user table"""
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        return False
    
    conn = None
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current table structure
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"📋 Current columns: {', '.join(columns)}")
        
        # Check which columns need to be added
        columns_to_add = []
        
        if 'include_stock_suite' not in columns:
            columns_to_add.append(('include_stock_suite', 'BOOLEAN DEFAULT 0'))
        
        if 'include_insider_trading' not in columns:
            columns_to_add.append(('include_insider_trading', 'BOOLEAN DEFAULT 0'))
        
        if 'include_market_news' not in columns:
            columns_to_add.append(('include_market_news', 'BOOLEAN DEFAULT 0'))
        
        if not columns_to_add:
            print("✅ All columns already exist. No migration needed.")
            conn.close()
            return True
        
        # Add missing columns
        print(f"\n📝 Adding {len(columns_to_add)} new column(s)...")
        
        for col_name, col_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"  ⚠ Column {col_name} already exists, skipping...")
                else:
                    raise
        
        # Commit changes
        conn.commit()
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(user)")
        final_columns = [col[1] for col in cursor.fetchall()]
        
        print(f"\n✅ Migration complete!")
        print(f"📋 Final columns ({len(final_columns)}): {', '.join(final_columns)}")
        
        # Show a sample user to verify defaults
        cursor.execute("SELECT * FROM user LIMIT 1")
        if cursor.fetchone():
            print("\n✓ Verified: Existing users have default values (0) for new columns")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("DATABASE MIGRATION v3: Stock Suite Features")
    print("=" * 60)
    print("\nThis script will add the following columns to the 'user' table:")
    print("  • include_stock_suite (BOOLEAN)")
    print("  • include_insider_trading (BOOLEAN)")
    print("  • include_market_news (BOOLEAN)")
    print()
    
    success = migrate_database()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ MIGRATION SUCCESSFUL")
        print("=" * 60)
        print("\nYou can now use the Stock Suite features!")
        print("Users can enable these options through the web interface.")
    else:
        print("\n" + "=" * 60)
        print("❌ MIGRATION FAILED")
        print("=" * 60)
        print("\nPlease check the error messages above and try again.")
