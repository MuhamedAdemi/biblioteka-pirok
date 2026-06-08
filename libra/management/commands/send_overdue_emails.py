"""
Komandë: python manage.py send_overdue_emails

Dërgon email rikujtues për të gjitha huazimet vonuara.
Mund të konfigurohet si detyrë e planifikuar (scheduled task) në PythonAnywhere.

Konfigurimi i email-it në PythonAnywhere Web tab → Environment variables:
  EMAIL_BACKEND   = django.core.mail.backends.smtp.EmailBackend
  EMAIL_HOST_USER = pirokbiblioteka@gmail.com
  EMAIL_HOST_PASSWORD = [fjalëkalimi i aplikacionit Gmail]
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from libra.models import Loan, Member


class Command(BaseCommand):
    help = 'Dërgon email rikujtues për huazimet vonuara'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Trego pa dërguar')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()

        # Shëno si vonuara
        updated = Loan.objects.filter(status='active', due_date__lt=today).update(status='overdue')
        if updated:
            self.stdout.write(f'  → Shënuar {updated} huazime si vonuara.')

        overdue = Loan.objects.filter(
            status='overdue'
        ).select_related('copy__book', 'member')

        if not overdue.exists():
            self.stdout.write('Nuk ka huazime vonuara.')
            return

        sent = failed = no_email = 0
        for loan in overdue:
            member = loan.member
            if not member.email:
                no_email += 1
                continue

            days_overdue = (today - loan.due_date).days
            is_critical  = days_overdue >= 365

            subject = ('⚠️ Biblioteka Pirok – Libër i Vonuar mbi 1 Vit'
                       if is_critical else
                       'Biblioteka Pirok – Rikujtim Kthimi / Return Reminder')

            if is_critical:
                body = self._critical_body(member, loan, days_overdue)
            else:
                body = self._reminder_body(member, loan, days_overdue)

            if dry_run:
                self.stdout.write(f'[DRY-RUN] → {member.email}: {subject[:60]}')
                sent += 1
                continue

            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [member.email])
                self.stdout.write(self.style.SUCCESS(f'  ✓ {member.email}'))
                sent += 1
            except Exception as e:
                self.stderr.write(f'  ✗ {member.email}: {e}')
                failed += 1

        self.stdout.write(f'\nGatova: {sent} dërguar, {failed} dështuan, {no_email} pa email.')

    def _reminder_body(self, member, loan, days_overdue):
        due_str = loan.due_date.strftime('%d.%m.%Y')
        title   = loan.copy.book.title
        nr      = loan.copy.copy_number
        name    = member.full_name()
        url     = 'https://bibliotekapirok.pythonanywhere.com/hyrje/'
        return f"""🇦🇱 SHQIP
================
I/E nderuar {name},

Afati i kthimit të librit "{title}" (Nr. {nr}) ka kaluar prej {days_overdue} ditësh.
Afati ishte: {due_str}.

Ju lutemi ktheni librin ose vazhdoni afatin online (maks. 2 herë):
{url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇲🇰 МАКЕДОНСКИ
================
Почитуван/а {name},

Рокот за враќање на книгата "{title}" (Бр. {nr}) помина пред {days_overdue} дена.
Рокот беше: {due_str}.

Ве молиме вратете ја книгата или обновете го рокот онлајн (макс. 2 пати):
{url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇬🇧 ENGLISH
===========
Dear {name},

The return deadline for "{title}" (No. {nr}) passed {days_overdue} days ago.
The deadline was: {due_str}.

Please return the book or renew your loan online (max. 2 times):
{url}

— Biblioteka Pirok | pirokbiblioteka@gmail.com"""

    def _critical_body(self, member, loan, days_overdue):
        due_str = loan.due_date.strftime('%d.%m.%Y')
        title   = loan.copy.book.title
        nr      = loan.copy.copy_number
        name    = member.full_name()
        return f"""⚠️ NJOFTIM I RËNDËSISHËM / ВАЖНО ИЗВЕСТУВАЊЕ / IMPORTANT NOTICE

🇦🇱 SHQIP
================
I/E nderuar {name},

Libri "{title}" (Nr. {nr}) është vonuar MBI 1 VIT ({days_overdue} ditë).
Afati i kthimit ishte: {due_str}.

Nëse libri nuk kthehet brenda 30 ditëve, biblioteka do të ndërmarrë hapa ligjorë
sipas kontratës së anëtarësisë. Do t'ju kërkohet të zëvendësoni librin dhe
të paguani 1.000 denarë shpenzime administrative.

Kontaktoni menjëherë: pirokbiblioteka@gmail.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇲🇰 МАКЕДОНСКИ
================
Почитуван/а {name},

Книгата "{title}" (Бр. {nr}) е задоцнета ПОВЕЌЕ ОД 1 ГОДИНА ({days_overdue} дена).
Рокот за враќање беше: {due_str}.

Доколку книгата не се врати во рок од 30 дена, библиотеката ќе преземе правни чекори
согласно договорот за членство. Ќе бидете обврзани да ја замените книгата и
да платите 1.000 денари административни трошоци.

Контактирајте веднаш: pirokbiblioteka@gmail.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇬🇧 ENGLISH
===========
Dear {name},

The book "{title}" (No. {nr}) is OVER 1 YEAR overdue ({days_overdue} days).
The return deadline was: {due_str}.

If the book is not returned within 30 days, the library will pursue legal action
as per the membership agreement. You will be required to replace the book and
pay 1,000 denars in administrative costs.

Contact us immediately: pirokbiblioteka@gmail.com

— Biblioteka Pirok"""
