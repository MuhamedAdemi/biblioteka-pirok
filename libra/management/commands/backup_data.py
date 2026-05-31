import os
import glob
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Krijon backup të të dhënave dhe mban vetëm 7 të fundit'

    def handle(self, *args, **options):
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        filename = os.path.join(backup_dir, f'backup_{timestamp}.json')

        with open(filename, 'w', encoding='utf-8') as f:
            call_command('dumpdata', 'libra', indent=2, stdout=f)

        size = os.path.getsize(filename) / 1024

        # Mban vetem 7 backupet e fundit
        old_backups = sorted(glob.glob(os.path.join(backup_dir, 'backup_*.json')))
        while len(old_backups) > 7:
            os.remove(old_backups.pop(0))

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Backup: {filename} ({size:.1f} KB) — {len(old_backups)} backup gjithsej'
            )
        )
