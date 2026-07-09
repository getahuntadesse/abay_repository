# setup_otp.py
import os
import sys
import subprocess

def run_command(cmd):
    print(f"\n▶ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result

def setup_otp():
    print("=" * 60)
    print("Setting up Django OTP")
    print("=" * 60)
    
    # Step 1: Check if django-otp is installed
    print("\nStep 1: Checking django-otp installation...")
    result = run_command("pip show django-otp")
    if "WARNING" in result.stdout or "not found" in result.stdout.lower():
        print("\n⚠️ django-otp not installed. Installing...")
        run_command("pip install django-otp")
    
    # Step 2: Make migrations
    print("\nStep 2: Creating OTP migrations...")
    run_command("python manage.py makemigrations django_otp")
    run_command("python manage.py makemigrations otp_email")
    run_command("python manage.py makemigrations otp_static")
    
    # Step 3: Apply migrations
    print("\nStep 3: Applying OTP migrations...")
    run_command("python manage.py migrate django_otp")
    run_command("python manage.py migrate otp_email")
    run_command("python manage.py migrate otp_static")
    
    # Step 4: Verify tables
    print("\nStep 4: Verifying OTP tables...")
    result = run_command('python manage.py dbshell -c "USE abay_repository; SHOW TABLES LIKE \'otp%\';"')
    
    print("\n" + "=" * 60)
    print("✅ OTP setup completed!")
    print("=" * 60)
    print("\nNow run: python manage.py runserver 3000")

if __name__ == "__main__":
    setup_otp()