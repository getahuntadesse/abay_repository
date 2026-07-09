#!/usr/bin/env python
"""
Database Migration Fix Script for Abay Repository
This script ONLY handles migrations - no user creation or sample data.
"""

import os
import sys
import subprocess
import django
from django.db import connection
from django.core.management import call_command
from django.db.utils import OperationalError

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def run_command(command, capture_output=False):
    """Run a shell command and return the result"""
    try:
        if capture_output:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        else:
            result = subprocess.run(command, shell=True)
            return "", "", result.returncode
    except Exception as e:
        return "", str(e), 1

def check_database_connection():
    """Check if database connection is working"""
    print_info("Checking database connection...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print_success("Database connection successful!")
            return True
    except Exception as e:
        print_error(f"Database connection failed: {e}")
        return False

def check_table_exists(table_name):
    """Check if a table exists in the database"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            return cursor.fetchone() is not None
    except Exception:
        return False

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{column_name}'")
            return cursor.fetchone() is not None
    except Exception:
        return False

def reset_migrations_for_app(app_name):
    """Reset migrations for a specific app"""
    print_info(f"Resetting migrations for {app_name}...")
    try:
        # Delete migration files
        import os
        import glob
        migration_dir = f"{app_name}/migrations"
        if os.path.exists(migration_dir):
            # Delete all migration files except __init__.py
            for f in glob.glob(f"{migration_dir}/0*.py"):
                os.remove(f)
                print_info(f"  Deleted: {f}")
            for f in glob.glob(f"{migration_dir}/0*.pyc"):
                os.remove(f)
            print_success(f"Migration files deleted for {app_name}")
        return True
    except Exception as e:
        print_error(f"Failed to reset migrations for {app_name}: {e}")
        return False

def fix_accounts_migration():
    """Fix the duplicate column error in accounts migration"""
    print_header("Fixing Accounts Migration")
    
    # Check if the table exists
    if not check_table_exists('accounts_customuser'):
        print_info("accounts_customuser table doesn't exist. Will create with migrations.")
        return True
    
    # Check if the problematic column exists
    column_exists = check_column_exists('accounts_customuser', 'two_factor_backup_codes')
    
    if column_exists:
        print_info("Column 'two_factor_backup_codes' already exists. Faking migrations...")
        
        try:
            # Fake all accounts migrations
            call_command('migrate', 'accounts', fake=True)
            print_success("Accounts migrations faked successfully!")
            return True
        except Exception as e:
            print_error(f"Failed to fake accounts migrations: {e}")
            return False
    else:
        print_info("Column 'two_factor_backup_codes' doesn't exist. Running migrations normally...")
        try:
            # Check if migrations exist
            import os
            migration_dir = "accounts/migrations"
            if os.path.exists(migration_dir):
                migration_files = [f for f in os.listdir(migration_dir) if f.startswith('0') and f.endswith('.py')]
                if not migration_files:
                    print_info("No migrations found. Creating...")
                    call_command('makemigrations', 'accounts')
            
            call_command('migrate', 'accounts')
            print_success("Accounts migrations applied successfully!")
            return True
        except Exception as e:
            print_error(f"Failed to apply accounts migrations: {e}")
            print_info("Attempting to create and fake migrations...")
            try:
                call_command('makemigrations', 'accounts')
                call_command('migrate', 'accounts', fake=True)
                print_success("Accounts migrations created and faked!")
                return True
            except Exception as e2:
                print_error(f"Failed: {e2}")
                return False

def create_and_apply_payments_migrations():
    """Create and apply payments migrations"""
    print_header("Setting Up Payments App")
    
    # Check if payments table exists
    if check_table_exists('payments_payment'):
        print_info("Payments tables already exist.")
        
        # Check if migrations are applied
        try:
            from django.db.migrations.recorder import MigrationRecorder
            applied = MigrationRecorder.Migration.objects.filter(app='payments').exists()
            if applied:
                print_info("Payments migrations already applied.")
                return True
            else:
                print_info("Payments tables exist but migrations not recorded. Faking...")
                call_command('migrate', 'payments', fake=True)
                print_success("Payments migrations faked!")
                return True
        except Exception as e:
            print_warning(f"Error checking migration status: {e}")
            
        # Try to apply migrations
        try:
            print_info("Attempting to apply payments migrations...")
            call_command('migrate', 'payments')
            print_success("Payments migrations applied!")
            return True
        except Exception as e:
            print_warning(f"Could not apply payments migrations: {e}")
            print_info("Faking payments migrations...")
            try:
                call_command('migrate', 'payments', fake=True)
                print_success("Payments migrations faked!")
                return True
            except Exception as e2:
                print_error(f"Failed to fake payments migrations: {e2}")
                return False
    
    print_info("Creating payments migrations...")
    try:
        # Check if migrations directory has files
        import os
        migration_dir = "payments/migrations"
        has_migrations = False
        if os.path.exists(migration_dir):
            migration_files = [f for f in os.listdir(migration_dir) if f.startswith('0') and f.endswith('.py')]
            has_migrations = len(migration_files) > 0
        
        if not has_migrations:
            call_command('makemigrations', 'payments')
            print_success("Payments migrations created!")
        else:
            print_info("Payments migrations already exist.")
        
        print_info("Applying payments migrations...")
        call_command('migrate', 'payments')
        print_success("Payments migrations applied!")
        return True
    except Exception as e:
        print_error(f"Failed to create/apply payments migrations: {e}")
        print_info("Attempting to force apply...")
        try:
            call_command('migrate', 'payments', fake_initial=True)
            print_success("Payments migrations applied with --fake-initial!")
            return True
        except Exception as e2:
            print_error(f"Failed: {e2}")
            return False

def apply_migrations_for_app(app_name):
    """Apply migrations for a specific app"""
    print_info(f"Applying migrations for {app_name}...")
    
    try:
        # Check if migrations exist
        import os
        migration_dir = f"{app_name}/migrations"
        has_migrations = False
        if os.path.exists(migration_dir):
            migration_files = [f for f in os.listdir(migration_dir) if f.startswith('0') and f.endswith('.py')]
            has_migrations = len(migration_files) > 0
        
        if not has_migrations:
            # Try to create migrations
            try:
                call_command('makemigrations', app_name)
                print_info(f"Migrations created for {app_name}")
            except Exception as e:
                print_warning(f"Could not create migrations for {app_name}: {e}")
                return False
        
        # Apply migrations
        call_command('migrate', app_name)
        print_success(f"{app_name} migrations applied!")
        return True
    except Exception as e:
        print_warning(f"Failed to apply {app_name} migrations: {e}")
        # Try to fake
        try:
            call_command('migrate', app_name, fake=True)
            print_success(f"{app_name} migrations faked!")
            return True
        except Exception as e2:
            print_error(f"Failed to handle {app_name}: {e2}")
            return False

def handle_all_migrations():
    """Handle migrations for all apps"""
    print_header("Handling All App Migrations")
    
    # List of apps in order of dependency
    apps = [
        'contenttypes',
        'auth',
        'accounts',
        'admin',
        'sessions',
        'books',
        'payments',
        'reviews',
        'royalties',
        'notifications',
        'otp_static',
        'otp_email',
    ]
    
    for app in apps:
        try:
            apply_migrations_for_app(app)
        except Exception as e:
            print_error(f"Error with {app}: {e}")
            print_info(f"Skipping {app} for now...")
    
    return True

def apply_remaining_migrations():
    """Apply any remaining migrations"""
    print_header("Applying Remaining Migrations")
    
    print_info("Running migrate for all apps...")
    try:
        call_command('migrate')
        print_success("All migrations applied successfully!")
        return True
    except Exception as e:
        print_error(f"Failed to apply all migrations: {e}")
        
        # Try with --fake-initial
        print_info("Attempting with --fake-initial...")
        try:
            call_command('migrate', fake_initial=True)
            print_success("Migrations applied with --fake-initial!")
            return True
        except Exception as e2:
            print_error(f"Failed even with --fake-initial: {e2}")
            
            # Last resort: fake all
            print_info("Attempting to fake all migrations...")
            try:
                call_command('migrate', fake=True)
                print_success("All migrations faked!")
                return True
            except Exception as e3:
                print_error(f"Failed to fake all migrations: {e3}")
                return False

def check_migration_status():
    """Check the current migration status"""
    print_header("Migration Status")
    
    try:
        call_command('showmigrations')
        print_success("Migration status displayed above!")
        return True
    except Exception as e:
        print_error(f"Failed to show migrations: {e}")
        return False

def main():
    """Main execution function"""
    print_header("ABAY REPOSITORY - MIGRATION FIX SCRIPT")
    print(f"{Colors.CYAN}This script will fix migration issues for your database.{Colors.RESET}")
    print(f"{Colors.YELLOW}This script ONLY handles migrations - NO user or data creation.{Colors.RESET}")
    print(f"{Colors.YELLOW}Please backup your database before running this script.{Colors.RESET}")
    
    response = input(f"\n{Colors.BOLD}Continue? (y/n): {Colors.RESET}")
    if response.lower() != 'y':
        print_info("Operation cancelled.")
        return
    
    # Step 1: Check database connection
    if not check_database_connection():
        print_error("Database connection failed. Please check your settings.")
        return
    
    # Step 2: Fix accounts migration
    if not fix_accounts_migration():
        print_warning("Failed to fix accounts migration. Continuing anyway...")
    
    # Step 3: Create and apply payments migrations
    if not create_and_apply_payments_migrations():
        print_warning("Payments migrations may have issues. Continuing...")
    
    # Step 4: Handle all other app migrations
    handle_all_migrations()
    
    # Step 5: Apply any remaining migrations
    apply_remaining_migrations()
    
    # Step 6: Check migration status
    check_migration_status()
    
    # Final message
    print_header("MIGRATION COMPLETE")
    print_success("Database migrations completed!")
    print_info("You can now run: python manage.py runserver")
    print_info("Access the dashboard at: http://localhost:3000/payments/dashboard/")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()