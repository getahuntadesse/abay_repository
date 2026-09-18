"""
Remove SVG/HTML/scriptable files left under MEDIA_ROOT (SAR 6.1 cleanup).
Usage: python manage.py purge_dangerous_media [--dry-run]
"""
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

BLOCKED = {
    ".svg", ".svgz", ".html", ".htm", ".xhtml", ".php", ".phtml",
    ".js", ".mjs", ".exe", ".sh", ".bat", ".asp", ".aspx", ".jsp",
}


class Command(BaseCommand):
    help = "Delete dangerous media files that can cause stored XSS"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT)
        if not root.exists():
            self.stdout.write("MEDIA_ROOT does not exist")
            return
        removed = 0
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in BLOCKED:
                self.stdout.write(f"{'Would delete' if options['dry_run'] else 'Deleting'}: {p}")
                if not options["dry_run"]:
                    p.unlink()
                removed += 1
        self.stdout.write(self.style.SUCCESS(f"Done. Files touched: {removed}"))
