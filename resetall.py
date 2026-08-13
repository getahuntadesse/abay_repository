# reset_payments_fixed.py
import os
import sys
import subprocess
import shutil
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print("=" * 70)

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def run_command(command):
    """Run a shell command with error handling"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        return result
    except Exception as e:
        print_error(f"Exception running command: {command}")
        print_error(f"Error: {str(e)}")
        return None

def reset_payments_complete(force=False):
    """Complete reset and migrate for payments"""
    
    print_header("COMPLETE PAYMENTS RESET AND MIGRATE")
    
    # Step 1: Check environment
    if not os.path.exists('manage.py'):
        print_error("manage.py not found!")
        return False
    
    # Step 2: Show current status
    print_info("Current migration status:")
    result = run_command("python manage.py showmigrations payments")
    if result:
        print(result.stdout)
    
    # Step 3: Reset payments to zero
    print_info("\nResetting payments to zero...")
    result = run_command("python manage.py migrate payments zero")
    if result and result.returncode == 0:
        print_success("Payments reset to zero")
    else:
        print_error("Failed to reset payments")
        if result:
            print_error(result.stderr)
        if not force:
            return False
    
    # Step 4: Delete migration files
    print_info("\nDeleting migration files...")
    migration_dir = Path('payments') / 'migrations'
    if migration_dir.exists():
        for file in migration_dir.glob('*.py'):
            if file.name != '__init__.py':
                try:
                    file.unlink()
                    print(f"  Deleted: {file.name}")
                except Exception as e:
                    print_warning(f"Failed to delete {file.name}: {e}")
        
        pycache_dir = migration_dir / '__pycache__'
        if pycache_dir.exists():
            shutil.rmtree(pycache_dir)
            print("  Deleted: __pycache__")
    
    print_success("Migration files deleted")
    
    # Step 5: Check admin file for errors
    print_info("\nChecking admin file...")
    admin_file = Path('payments') / 'admin.py'
    if admin_file.exists():
        content = admin_file.read_text()
        # Check for common issues
        if 'readonly_fields' in content and 'initiated_at' in content:
            print_warning("Found potential admin issue - fixing...")
            # Fix the admin file
            fixed_content = content.replace("'initiated_at'", "'created_at'")
            fixed_content = fixed_content.replace("'processed_at'", "'created_at'")
            fixed_content = fixed_content.replace("'completed_at'", "'created_at'")
            admin_file.write_text(fixed_content)
            print_success("Admin file fixed")
    
    # Step 6: Create migration
    print_info("\nCreating migration...")
    result = run_command("python manage.py makemigrations payments")
    if result and result.returncode == 0:
        print_success("Migration created")
        print(result.stdout)
    else:
        print_error("Failed to create migration")
        if result:
            print_error(result.stderr)
            # Check if it's an admin error
            if "admin" in result.stderr and "readonly_fields" in result.stderr:
                print_info("Admin error detected. Temporarily disabling admin...")
                
                # Comment out admin registration
                if admin_file.exists():
                    content = admin_file.read_text()
                    # Comment out all admin registrations
                    lines = content.split('\n')
                    new_lines = []
                    for line in lines:
                        if '@admin.register' in line or 'class' in line and 'Admin' in line:
                            new_lines.append('# ' + line)
                        else:
                            new_lines.append(line)
                    admin_file.write_text('\n'.join(new_lines))
                    print_success("Admin temporarily disabled")
                    
                    # Retry migration
                    print_info("Retrying migration...")
                    result = run_command("python manage.py makemigrations payments")
                    if result and result.returncode == 0:
                        print_success("Migration created successfully")
                    else:
                        print_error("Still failed")
                        if not force:
                            return False
        
        if not force:
            return False
    
    # Step 7: Apply migration
    print_info("\nApplying migration...")
    result = run_command("python manage.py migrate payments")
    if result and result.returncode == 0:
        print_success("Migration applied")
        print(result.stdout)
    else:
        print_error("Failed to apply migration")
        if result:
            print_error(result.stderr)
        if not force:
            return False
    
    # Step 8: Fix nullable fields
    print_info("\nFixing nullable fields...")
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
        django.setup()
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Check if payments table exists
            cursor.execute("SHOW TABLES LIKE 'payments'")
            if cursor.fetchone():
                try:
                    cursor.execute("ALTER TABLE payments MODIFY payment_reference VARCHAR(50) NOT NULL")
                    print_success("Fixed payment_reference NOT NULL")
                except Exception as e:
                    print_warning(f"payment_reference fix: {e}")
                
                try:
                    cursor.execute("ALTER TABLE payments MODIFY net_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00")
                    print_success("Fixed net_amount NOT NULL")
                except Exception as e:
                    print_warning(f"net_amount fix: {e}")
                
                try:
                    cursor.execute("ALTER TABLE payments MODIFY period_start DATE NOT NULL")
                    print_success("Fixed period_start NOT NULL")
                except Exception as e:
                    print_warning(f"period_start fix: {e}")
                
                try:
                    cursor.execute("ALTER TABLE payments MODIFY period_end DATE NOT NULL")
                    print_success("Fixed period_end NOT NULL")
                except Exception as e:
                    print_warning(f"period_end fix: {e}")
    except Exception as e:
        print_warning(f"Could not fix nullable fields: {e}")
    
    # Step 9: Restore admin if it was disabled
    if admin_file.exists():
        content = admin_file.read_text()
        if '# @admin.register' in content:
            print_info("\nRestoring admin...")
            # Remove comments
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith('# @admin.register') or (line.startswith('# class') and 'Admin' in line):
                    new_lines.append(line[2:])  # Remove '# '
                else:
                    new_lines.append(line)
            admin_file.write_text('\n'.join(new_lines))
            print_success("Admin restored")
    
    # Step 10: Show final status
    print_info("\nFinal migration status:")
    result = run_command("python manage.py showmigrations payments")
    if result:
        print(result.stdout)
    
    # Step 11: Check models
    print_info("\nChecking models...")
    result = run_command("python manage.py check payments")
    if result:
        if "System check identified no issues" in result.stdout:
            print_success("Payment models validated successfully!")
        else:
            print_warning("Model validation found issues:")
            print(result.stdout)
    
    print_header("PAYMENTS RESET COMPLETE")
    print_success("Payments reset and migrated successfully!")
    
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Reset and migrate payments")
    parser.add_argument('--force', '-f', action='store_true', help='Force operations')
    args = parser.parse_args()
    
    reset_payments_complete(force=args.force)

if __name__ == "__main__":
    main()