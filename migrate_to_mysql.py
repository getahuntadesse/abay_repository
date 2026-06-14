#!/usr/bin/env python
"""
Complete migration script from SQLite to MySQL
Run this after updating settings.py
"""

import os
import subprocess
import sys

def run_command(command):
    """Run shell command and print output"""
    print(f"\n>>> {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode == 0

def check_mysql():
    """Check if MySQL is running"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 3306))
    sock.close()
    return result == 0

def migrate_to_mysql():
    """Complete migration from SQLite to MySQL"""
    
    print("=" * 60)
    print("COMPLETE MIGRATION TO MYSQL")
    print("=" * 60)
    
    # Step 1: Check if MySQL is running
    print("\n1. Checking if MySQL is running...")
    if not check_mysql():
        print("\n✗ MySQL is not running!")
        print("Please start MySQL in XAMPP Control Panel first.")
        print("1. Open XAMPP Control Panel")
        print("2. Click 'Start' next to MySQL")
        print("3. Run this script again")
        return False
    
    print("✓ MySQL is running!")
    
    # Step 2: Export data from SQLite (if exists)
    if os.path.exists('db.sqlite3'):
        print("\n2. Exporting data from SQLite...")
        if not run_command('python manage.py dumpdata --exclude contenttypes --exclude auth.permission > backup.json'):
            print("⚠ Warning: Could not export all data")
    else:
        print("\n2. No SQLite database found, skipping export...")
    
    # Step 3: Install mysqlclient
    print("\n3. Installing mysqlclient...")
    run_command('pip install mysqlclient')
    
    # Step 4: Clean old migrations
    print("\n4. Cleaning old migration files...")
    if os.path.exists('fix_migrations.py'):
        run_command('python fix_migrations.py')
    
    # Step 5: Create new migrations
    print("\n5. Creating new migrations...")
    if not run_command('python manage.py makemigrations'):
        print("✗ Failed to create migrations!")
        return False
    
    # Step 6: Apply migrations to MySQL
    print("\n6. Applying migrations to MySQL...")
    if not run_command('python manage.py migrate'):
        print("✗ Failed to apply migrations!")
        return False
    
    # Step 7: Load data (if backup exists)
    if os.path.exists('backup.json'):
        print("\n7. Loading data into MySQL...")
        load_result = run_command('python manage.py loaddata backup.json')
        if not load_result:
            print("⚠ Warning: Could not load all data. You may need to re-enter some data.")
    
    # Step 8: Create superuser
    print("\n8. Creating superuser...")
    run_command('python manage.py createsuperuser')
    
    # Step 9: Collect static files
    print("\n9. Collecting static files...")
    run_command('python manage.py collectstatic --noinput')
    
    print("\n" + "=" * 60)
    print("✓ MIGRATION COMPLETE!")
    print("=" * 60)
    print("\n📊 Database: MySQL (XAMPP)")
    print("📍 phpMyAdmin: http://localhost/phpmyadmin")
    print("🔑 MySQL: root / (no password)")
    print("\nNext steps:")
    print("  1. Run: python manage.py runserver")
    print("  2. Visit: http://127.0.0.1:8000/admin")
    print("  3. Login with your superuser credentials")
    
    return True

if __name__ == "__main__":
    success = migrate_to_mysql()
    if not success:
        sys.exit(1)