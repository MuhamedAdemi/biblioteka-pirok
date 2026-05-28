import uuid
from django.db import models


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
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    title = models.CharField(max_length=500, verbose_name="Titulli")
    subtitle = models.CharField(max_length=500, blank=True, verbose_name="Nëntitulli")
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
    subjects = models.ManyToManyField(Subject, blank=True, verbose_name="Kategorite")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Sasia")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def primary_author(self):
        ba = self.book_authors.filter(role='primary').first()
        return ba.author if ba else None

    def available_copies(self):
        loaned = self.loan_set.filter(status='active').count()
        return self.quantity - loaned


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


class Member(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    first_name = models.CharField(max_length=150, verbose_name="Emri")
    last_name = models.CharField(max_length=150, verbose_name="Mbiemri")
    email = models.EmailField(blank=True, verbose_name="Email")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefoni")
    address = models.TextField(blank=True, verbose_name="Adresa")
    membership_number = models.CharField(max_length=50, unique=True, verbose_name="Nr. Anëtarësisë")
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
        return self.loan_set.filter(status='active').count()


class Loan(models.Model):
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('returned', 'Kthyer'),
        ('overdue', 'Vonuar'),
    ]
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Libri")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="Anëtari")
    loan_date = models.DateField(auto_now_add=True, verbose_name="Data e Huazimit")
    due_date = models.DateField(verbose_name="Data e Kthimit")
    return_date = models.DateField(null=True, blank=True, verbose_name="Kthyer më")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Statusi"
    )
    notes = models.TextField(blank=True, verbose_name="Shënime")

    class Meta:
        ordering = ['-loan_date']

    def __str__(self):
        return f"{self.book.title} → {self.member}"
