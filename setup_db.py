from app import app, db

print("Starting database setup...")

with app.app_context():
    print("Creating all tables...")
    db.create_all()
    print("✅ Tables created successfully!")
    
    # Verify tables were created
    import sqlite3
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("\n📁 TABLES IN DATABASE:")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Check payment table columns
    cursor.execute("PRAGMA table_info(payment)")
    payment_cols = cursor.fetchall()
    
    print("\n💳 PAYMENT TABLE COLUMNS:")
    for col in payment_cols:
        print(f"   - {col[1]} ({col[2]})")
    
    # Check user table columns
    cursor.execute("PRAGMA table_info(user)")
    user_cols = cursor.fetchall()
    
    print("\n👤 USER TABLE COLUMNS:")
    for col in user_cols:
        print(f"   - {col[1]} ({col[2]})")
    
    conn.close()
    
print("\n✅ Database setup complete! You can now run: python app.py")