import uuid
from django.db import models
from django.contrib.auth.models import User


class Publisher(models.Model):
    name = models.CharField(max_length=300)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        if self.city:
            return f"{self.city} : {self.name}"
        return self.name


class Author(models.Model):
    last_name = models.CharField(max_length=150)
    first_name = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        if self.first_name:
            return f"{self.last_name}, {self.first_name}"
        return self.last_name


class Subject(models.Model):
    name = models.CharField(max_length=300, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Book(models.Model):
    LANGUAGE_CHOICES = [
        ('sq', 'Shqip'),
        ('en', 'Anglisht'),
        ('mk', 'Maqedonisht'),
        ('other', 'Gjuhë tjera'),
    ]
    LANGUAGE_PREFIX = {
        'sq': '101',
        'en': '201',
        'mk': '301',
        'other': '501',
    }

    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    title = models.CharField(max_length=500, verbose_name="Titulli")
    subtitle = models.CharField(max_length=500, blank=True, verbose_name="Nëntitulli")
    language = models.CharField(
        max_length=10, choices=LANGUAGE_CHOICES, default='sq', verbose_name="Gjuha"
    )
    isbn = models.CharField(max_length=20, blank=True, verbose_name="ISBN")
    publisher = models.ForeignKey(
        Publisher, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="Botuesi"
    )
    year = models.CharField(max_length=30, blank=True, verbose_name="Viti")
    format = models.CharField(max_length=50, blank=True, verbose_name="Formati (cm)")
    pages = models.CharField(max_length=50, blank=True, verbose_name="Faqet")
    class_number = models.CharField(max_length=50, blank=True, verbose_name="Nr. Klasifikimit")
    general_note = models.TextField(blank=True, verbose_name="Shënime të përgjithshme")
    contents_note = models.TextField(blank=True, verbose_name="Shënime mbi përmbajtjen")
    summary = models.TextField(blank=True, verbose_name="Përmbledhje")
    subjects = models.ManyToManyField(Subject, blank=True, verbose_name="Kategoritë")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def primary_author(self):
        ba = self.book_authors.filter(role='primary').first()
        return ba.author if ba else None

    def total_copies(self):
        return self.copies.count()

    def available_copies(self):
        on_loan_ids = Loan.objects.filter(
            copy__book=self,
            status__in=['active', 'overdue']
        ).values_list('copy_id', flat=True).distinct()
        return self.copies.exclude(pk__in=on_loan_ids).count()


class BookAuthor(models.Model):
    ROLE_CHOICES = [
        ('primary', 'Autor Kryesor'),
        ('coauthor', 'Koautor'),
        ('editor', 'Editor / Redaktor'),
        ('translator', 'Përkthyes'),
    ]
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='book_authors')
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='primary')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'role']

    def __str__(self):
        return f"{self.author} ({self.get_role_display()})"


class BookCopy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='copies', verbose_name="Libri")
    copy_number = models.CharField(max_length=14, unique=True, verbose_name="Nr. Kopjes (Barkod)")
    shelf_label = models.CharField(max_length=12, blank=True, verbose_name="Label Rafti (p.sh. 3-00001)")
    notes = models.CharField(max_length=200, blank=True, verbose_name="Shënime")

    class Meta:
        ordering = ['copy_number']
        verbose_name = "Kopje Libri"
        verbose_name_plural = "Kopjet e Librave"

    def __str__(self):
        return f"[{self.copy_number}] {self.book.title}"

    def is_available(self):
        return not self.loan_set.filter(status__in=['active', 'overdue']).exists()

    @classmethod
    def suggest_shelf_label(cls, class_number=''):
        if not class_number:
            return ''
        try:
            first_digit = str(int(float(class_number.strip()[0])))
        except (ValueError, IndexError):
            first_digit = '0'
        last = cls.objects.filter(
            shelf_label__startswith=f'{first_digit}-'
        ).order_by('-shelf_label').first()
        if last and last.shelf_label:
            try:
                num = int(last.shelf_label.split('-')[1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{first_digit}-{str(num).zfill(5)}"

    @classmethod
    def next_copy_number(cls, language='sq'):
        prefix = Book.LANGUAGE_PREFIX.get(language, '501')
        last = cls.objects.filter(
            copy_number__startswith=f'{prefix}-'
        ).order_by('-copy_number').first()
        if last:
            try:
                num = int(last.copy_number.split('-')[1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{prefix}-{str(num).zfill(6)}"


class Member(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="Llogaria", related_name='member'
    )
    first_name = models.CharField(max_length=150, verbose_name="Emri")
    last_name = models.CharField(max_length=150, verbose_name="Mbiemri")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefoni")
    address = models.TextField(blank=True, verbose_name="Adresa")
    membership_number = models.CharField(max_length=8, unique=True, verbose_name="Nr. Anëtarësisë")
    membership_date = models.DateField(auto_now_add=True, verbose_name="Data e Anëtarësimit")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    notes = models.TextField(blank=True, verbose_name="Shënime")

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name}, {self.first_name} [{self.membership_number}]"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def active_loans(self):
        return self.loan_set.filter(status__in=['active', 'overdue']).count()


class Loan(models.Model):
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('returned', 'Kthyer'),
        ('overdue', 'Vonuar'),
    ]
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE, verbose_name="Kopja e Librit")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="Anëtari")
    loan_date = models.DateField(auto_now_add=True, verbose_name="Data e Huazimit")
    due_date = models.DateField(verbose_name="Afati i Kthimit")
    return_date = models.DateField(null=True, blank=True, verbose_name="Kthyer më")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Statusi"
    )
    renewals_count = models.PositiveIntegerField(default=0, verbose_name="Nr. Vazhdimeve")
    notes = models.TextField(blank=True, verbose_name="Shënime")

    class Meta:
        ordering = ['-loan_date']

    def __str__(self):
        return f"{self.copy.book.title} → {self.member}"

    @property
    def book(self):
        return self.copy.book

    def can_renew(self):
        return self.status in ['active', 'overdue'] and self.renewals_count < 2
