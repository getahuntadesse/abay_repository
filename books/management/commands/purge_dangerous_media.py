# books/management/commands/purge_dangerous_media.py
# Run once after deploy:  python manage.py purge_dangerous_media --dry-run
#                         python manage.py purge_dangerous_media

from django.core.management.base import BaseCommand
from django.conf import settings
import os

DANGEROUS_EXTS = {
    ".svg", ".svgz", ".html", ".htm", ".xhtml", ".php", ".phtml",
    ".js", ".mjs", ".exe", ".sh", ".bat",
}


class Command(BaseCommand):
    help = "Delete dangerous uploaded media (SVG, HTML, etc.) that can cause stored XSS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List files that would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        root = settings.MEDIA_ROOT
        dry = options["dry_run"]
        removed = 0
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext in DANGEROUS_EXTS:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, root)
                    if dry:
                        self.stdout.write(f"[dry-run] would delete: {rel}")
                    else:
                        try:
                            os.remove(full)
                            self.stdout.write(self.style.SUCCESS(f"deleted: {rel}"))
                            removed += 1
                        except OSError as e:
                            self.stderr.write(f"failed {rel}: {e}")
        if dry:
            self.stdout.write("Dry-run complete. Re-run without --dry-run to delete.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Removed {removed} dangerous file(s)."))
