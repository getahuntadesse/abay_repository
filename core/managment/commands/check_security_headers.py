# core/management/commands/check_security_headers.py
"""
Management command to check security headers.
"""

from django.core.management.base import BaseCommand
from django.test import Client
from django.conf import settings


class Command(BaseCommand):
    help = 'Check security headers on the site'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            default='/',
            help='URL to check (default: /)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show all headers'
        )
    
    def handle(self, *args, **options):
        client = Client()
        url = options['url']
        verbose = options['verbose']
        
        try:
            response = client.get(url)
            headers = response.headers
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching {url}: {e}"))
            return
        
        required_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': None,
            'Permissions-Policy': None,
            'Strict-Transport-Security': None,
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin',
        }
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"   SECURITY HEADERS CHECK - {url}")
        self.stdout.write("=" * 60 + "\n")
        
        all_present = True
        for header, expected_value in required_headers.items():
            if header in headers:
                value = headers[header]
                status = "✅"
                if expected_value and expected_value not in value:
                    status = "⚠️"
                    all_present = False
                self.stdout.write(f"{status} {header}: {value}")
            else:
                self.stdout.write(f"❌ {header}: MISSING")
                all_present = False
        
        if verbose:
            self.stdout.write("\n" + "-" * 60)
            self.stdout.write("   ALL HEADERS")
            self.stdout.write("-" * 60)
            for key, value in headers.items():
                self.stdout.write(f"{key}: {value}")
        
        self.stdout.write("\n" + "=" * 60)
        if all_present:
            self.stdout.write(self.style.SUCCESS("✅ ALL SECURITY HEADERS PRESENT"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ SOME SECURITY HEADERS MISSING"))
        self.stdout.write("=" * 60 + "\n")