import difflib
import secrets
import string as _string

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone

from .models import Book, Author, Publisher, Member, Loan, Subject, BookAuthor, BookCopy, BarcodeLog
from .forms import (
    BookForm, BookAuthorFormSet, BookCopyForm,
    MemberForm, LoanForm, LoanReturnForm,
    QuickReturnForm, QuickLoanForm,
    StaffCreateForm, SearchForm, AuthorForm, PublisherForm,
)


# ── PUBLIC ────────────────────────────────────────────────────────────────────

def home(request):
    recent_books = Book.objects.all().order_by('-created')[:8]
    total_books = Book.objects.count()
    total_members = Member.objects.filter(is_active=True).count()
    active_loans = Loan.objects.filter(status='active').count()
    return render(request, 'libra/home.html', {
        'recent_books': recent_books,
        'total_books': total_books,
        'total_members': total_members,
        'active_loans': active_loans,
    })


def catalog(request):
    books = Book.objects.all().prefetch_related('book_authors__author', 'subjects')
    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(
            Q(title__icontains=q) |
            Q(subtitle__icontains=q) |
            Q(isbn__icontains=q) |
            Q(book_authors__author__last_name__icontains=q) |
            Q(book_authors__author__first_name__icontains=q) |
            Q(publisher__name__icontains=q) |
            Q(subjects__name__icontains=q) |
            Q(class_number__icontains=q)
        ).distinct()
    subject_filter = request.GET.get('subject', '')
    if subject_filter:
        books = books.filter(subjects__id=subject_filter)
    subjects = Subject.objects.all()
    return render(request, 'libra/catalog.html', {
        'books': books, 'q': q,
        'subjects': subjects, 'subject_filter': subject_filter,
    })


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    primary_authors = book.book_authors.filter(role='primary').select_related('author')
    secondary_authors = book.book_authors.exclude(role='primary').select_related('author')
    copies = book.copies.all()
    return render(request, 'libra/book_detail.html', {
        'book': book,
        'primary_authors': primary_authors,
        'secondary_authors': secondary_authors,
        'copies': copies,
    })


def about(request):
    return render(request, 'libra/about.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', 'Kontakt')
        message = request.POST.get('message', '').strip()
        if name and email and message:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                full_subject = f'[Biblioteka Pirok] {subject} – nga {name}'
                body = f'Emri: {name}\nEmail: {email}\nTema: {subject}\n\n{message}'
                send_mail(
                    subject=full_subject,
                    message=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'pirokbiblioteka@gmail.com'),
                    recipient_list=[getattr(settings, 'CONTACT_EMAIL', 'pirokbiblioteka@gmail.com')],
                    fail_silently=False,
                )
                messages.success(request, f'Faleminderit {name}! Mesazhi juaj u dërgua. Do t\'ju kontaktojmë së shpejti.')
            except Exception:
                messages.warning(
                    request,
                    'Mesazhi nuk u dërgua. Ju lutem na kontaktoni drejtpërdrejt: pirokbiblioteka@gmail.com'
                )
        else:
            messages.error(request, 'Ju lutem plotësoni të gjitha fushat e detyrueshme.')
    return redirect('home')


# ── MEMBER DASHBOARD ──────────────────────────────────────────────────────────

def member_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.is_staff:
        return redirect('home')
    try:
        member = request.user.member
    except Exception:
        messages.error(request, 'Llogaria juaj nuk është e lidhur me asnjë anëtar.')
        return redirect('home')

    _mark_overdue()
    active_loans = member.loan_set.filter(
        status__in=['active', 'overdue']
    ).select_related('copy__book').order_by('due_date')
    loan_history = member.loan_set.filter(
        status='returned'
    ).select_related('copy__book').order_by('-return_date')[:10]

    return render(request, 'libra/member_dashboard.html', {
        'member': member,
        'active_loans': active_loans,
        'loan_history': loan_history,
    })


def loan_renew(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if not request.user.is_authenticated:
        return redirect('login')

    is_owner = (
        hasattr(request.user, 'member') and
        request.user.member == loan.member
    )
    if not is_owner and not request.user.is_staff:
        messages.error(request, 'Nuk keni leje për këtë veprim.')
        return redirect('home')

    if not loan.can_renew():
        messages.error(request, 'Ky huazim nuk mund të vazhdohet (u arrit kufiri i 2 vazhdimeve).')
        return redirect('member_dashboard' if is_owner else 'loan_list')

    if request.method == 'POST':
        loan.due_date = loan.due_date + timezone.timedelta(days=14)
        loan.renewals_count += 1
        loan.status = 'active'
        loan.save()
        messages.success(request, f'Huazimi u vazhdua. Afati i ri: {loan.due_date}')
        return redirect('member_dashboard' if is_owner else 'loan_list')

    return render(request, 'libra/loan_renew.html', {'loan': loan})


# ── ISBN CHECK ────────────────────────────────────────────────────────────────

@login_required
def book_isbn_check(request):
    isbn = request.GET.get('isbn', '').strip().replace('-', '').replace(' ', '')
    found = None
    if isbn:
        found = Book.objects.filter(isbn__icontains=isbn).first()
    return render(request, 'libra/book_isbn_check.html', {
        'isbn': isbn,
        'found': found,
    })


# ── AUTHOR SEARCH (AJAX autocomplete) ────────────────────────────────────────

@login_required
def _fuzzy_find(all_objects, str_fn, query, limit=10, cutoff=0.68):
    """
    Kërkim me tre strategji: icontains → ndarje fjalësh → difflib fuzzy.
    Kthehet lista objektesh (max limit).
    """
    q_lower = query.lower()
    words   = q_lower.split()
    scored  = {}  # pk → (obj, score)

    for obj in all_objects:
        text  = str_fn(obj).lower()
        parts = text.split()
        score = 0.0

        # Strategji 1: fraza e plotë
        if q_lower in text:
            score = 2.0

        # Strategji 2: çdo fjalë e pyetjes si nënstring
        if score == 0:
            for w in words:
                if w in text:
                    score += 1.0

        # Strategji 3: difflib fuzzy midis fjalëve (gjen gabime shkrimi)
        if score == 0 and len(q_lower) >= 3:
            for w in words:
                if len(w) < 3:
                    continue
                for p in parts:
                    if len(p) < 3:
                        continue
                    r = difflib.SequenceMatcher(None, w, p).ratio()
                    if r >= cutoff:
                        score += r * 0.7
                        break

        if score > 0:
            scored[obj.pk] = (obj, score)

    sorted_res = sorted(scored.values(), key=lambda x: -x[1])
    return [obj for obj, _ in sorted_res[:limit]]


def author_search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})
    all_authors = list(Author.objects.all())
    results = _fuzzy_find(all_authors, lambda a: f"{a.last_name} {a.first_name}", q)
    return JsonResponse({'results': [{'id': a.pk, 'text': str(a)} for a in results]})


@login_required
def publisher_search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})
    all_pubs = list(Publisher.objects.all())
    results  = _fuzzy_find(all_pubs, lambda p: p.name, q)
    return JsonResponse({'results': [{'id': p.pk, 'text': str(p)} for p in results]})


# ── BOOK MANAGEMENT ───────────────────────────────────────────────────────────

@login_required
def book_add(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        formset = BookAuthorFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            book = form.save()
            formset.instance = book
            formset.save()
            messages.success(request, f'Libri "{book.title}" u shtua. Shto kopjet fizike më poshtë.')
            return redirect('book_copy_list', pk=book.pk)
    else:
        isbn_initial = request.GET.get('isbn', '')
        form = BookForm(initial={'isbn': isbn_initial})
        formset = BookAuthorFormSet()
    return render(request, 'libra/book_form.html', {
        'form': form, 'formset': formset, 'action': 'Shto Libër',
        'existing_authors_json': '[]',
        'initial_publisher_json': 'null',
        'book': None,
        'copies': None,
    })


@login_required
def book_edit(request, pk):
    import json as _json
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        formset = BookAuthorFormSet(request.POST, instance=book)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Libri "{book.title}" u përditësua.')
            return redirect('book_detail', pk=book.pk)
    else:
        form = BookForm(instance=book)
        formset = BookAuthorFormSet(instance=book)
    existing_authors = [
        {'id': ba.author.pk, 'text': str(ba.author)}
        for ba in book.book_authors.select_related('author').all()
    ]
    initial_publisher = None
    if book.publisher:
        initial_publisher = {'id': str(book.publisher.pk), 'text': str(book.publisher)}
    copies = book.copies.select_related('book').all()
    return render(request, 'libra/book_form.html', {
        'form': form, 'formset': formset, 'action': 'Ndrysho Libër', 'book': book,
        'existing_authors_json': _json.dumps(existing_authors),
        'initial_publisher_json': _json.dumps(initial_publisher),
        'copies': copies,
    })


@login_required
def book_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, 'Vetëm administratori mund të fshijë libra.')
        return redirect('book_detail', pk=pk)
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Libri "{title}" u fshi.')
        return redirect('catalog')
    return render(request, 'libra/book_confirm_delete.html', {'book': book})


# ── BOOK COPIES ───────────────────────────────────────────────────────────────

@login_required
def book_copy_list(request, pk):
    book = get_object_or_404(Book, pk=pk)
    copies = book.copies.all()
    return render(request, 'libra/book_copy_list.html', {'book': book, 'copies': copies})


_LANG_PREFIX = {'sq': '101', 'mk': '201', 'en': '301', 'other': '401'}
_LANG_NAMES  = {'sq': 'Shqip', 'mk': 'Maqedonisht', 'en': 'Anglisht', 'other': 'Gjuhë tjera'}
_PREFIX_LANG = {v: k for k, v in _LANG_PREFIX.items()}

@login_required
def book_copy_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    expected_prefix   = _LANG_PREFIX.get(book.language) if book.language else None
    language_display  = _LANG_NAMES.get(book.language, '') if book.language else ''

    prefix_error = None

    if request.method == 'POST':
        form = BookCopyForm(request.POST)
        if form.is_valid():
            copy_number    = form.cleaned_data['copy_number']
            entered_prefix = copy_number[:3]

            if not expected_prefix:
                prefix_error = 'no_language'
            elif entered_prefix != expected_prefix:
                entered_lang = _LANG_NAMES.get(_PREFIX_LANG.get(entered_prefix, ''), 'gjuhë tjetër')
                prefix_error = (
                    f'Kodi <strong>{copy_number}</strong> është për gjuhën '
                    f'<strong>{entered_lang}</strong>. Ky libër është '
                    f'<strong>{language_display}</strong> — duhet prefiks '
                    f'<strong>{expected_prefix}</strong>.'
                )
            else:
                copy = form.save(commit=False)
                copy.book = book
                copy.shelf_label = BookCopy.suggest_shelf_label(book.class_number)
                copy.save()
                messages.success(request, f'Kopja [{copy.copy_number}] u shtua.')
                total_labels = BookCopy.objects.filter(shelf_label__gt='').count()
                if total_labels > 0 and total_labels % 56 == 0:
                    messages.info(
                        request,
                        f'Faqe etikete e plotë — {total_labels} etiketa ({total_labels // 56} × 56). '
                        f'Shko te Etiketa Rafti dhe printo faqen e re.'
                    )
                return redirect('book_copy_list', pk=pk)
    else:
        form = BookCopyForm()

    return render(request, 'libra/book_copy_form.html', {
        'form': form,
        'book': book,
        'class_number': book.class_number,
        'expected_prefix':  expected_prefix,
        'language_display': language_display,
        'prefix_error':     prefix_error,
    })


@login_required
def book_copy_delete(request, copy_pk):
    if not request.user.is_superuser:
        messages.error(request, 'Vetëm administratori mund të fshijë kopje.')
        return redirect('catalog')
    copy = get_object_or_404(BookCopy, pk=copy_pk)
    book_pk = copy.book.pk
    if request.method == 'POST':
        if copy.loan_set.filter(status__in=['active', 'overdue']).exists():
            messages.error(request, 'Nuk mund të fshihet kopja — ka huazim aktiv.')
        else:
            copy.delete()
            messages.success(request, 'Kopja u fshi.')
    return redirect('book_copy_list', pk=book_pk)


# ── AUTHORS & PUBLISHERS ──────────────────────────────────────────────────────

@login_required
def author_list(request):
    q = request.GET.get('q', '').strip()
    authors = Author.objects.annotate(book_count=Count('bookauthor', distinct=True))
    if q:
        authors = authors.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q)
        )
    authors = authors.order_by('last_name', 'first_name')
    return render(request, 'libra/author_list.html', {'authors': authors, 'q': q})


@login_required
def author_add(request):
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            author = form.save()
            messages.success(request, f'Autori "{author}" u shtua.')
            return redirect('author_list')
    else:
        form = AuthorForm()
    return render(request, 'libra/author_form.html', {'form': form, 'action': 'Shto Autor'})


@login_required
def author_edit(request, pk):
    author = get_object_or_404(Author, pk=pk)
    if request.method == 'POST':
        form = AuthorForm(request.POST, instance=author)
        if form.is_valid():
            form.save()
            messages.success(request, f'Autori u përditësua.')
            return redirect('author_list')
    else:
        form = AuthorForm(instance=author)
    return render(request, 'libra/author_form.html', {
        'form': form, 'action': 'Ndrysho Autor', 'author': author
    })


@login_required
def publisher_list(request):
    q = request.GET.get('q', '').strip()
    publishers = Publisher.objects.annotate(book_count=Count('book', distinct=True))
    if q:
        publishers = publishers.filter(
            Q(name__icontains=q) | Q(city__icontains=q)
        )
    publishers = publishers.order_by('name')
    return render(request, 'libra/publisher_list.html', {'publishers': publishers, 'q': q})


@login_required
def publisher_add(request):
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            pub = form.save()
            messages.success(request, f'Botuesi "{pub}" u shtua.')
            return redirect('publisher_list')
    else:
        form = PublisherForm()
    return render(request, 'libra/publisher_form.html', {'form': form, 'action': 'Shto Botues'})


@login_required
def publisher_edit(request, pk):
    pub = get_object_or_404(Publisher, pk=pk)
    if request.method == 'POST':
        form = PublisherForm(request.POST, instance=pub)
        if form.is_valid():
            form.save()
            messages.success(request, 'Botuesi u përditësua.')
            return redirect('publisher_list')
    else:
        form = PublisherForm(instance=pub)
    return render(request, 'libra/publisher_form.html', {
        'form': form, 'action': 'Ndrysho Botues', 'publisher': pub
    })


@login_required
def author_delete(request, pk):
    author = get_object_or_404(Author, pk=pk)
    if request.method == 'POST':
        name = str(author)
        author.delete()
        messages.success(request, f'Autori "{name}" u fshi.')
    return redirect('author_list')


@login_required
def publisher_delete(request, pk):
    pub = get_object_or_404(Publisher, pk=pk)
    if request.method == 'POST':
        name = str(pub)
        pub.delete()
        messages.success(request, f'Botuesi "{name}" u fshi.')
    return redirect('publisher_list')


@login_required
def subject_list(request):
    q = request.GET.get('q', '').strip()
    subjects = Subject.objects.annotate(book_count=Count('book', distinct=True))
    if q:
        subjects = subjects.filter(name__icontains=q)
    subjects = subjects.order_by('name')
    return render(request, 'libra/subject_list.html', {'subjects': subjects, 'q': q})


@login_required
def subject_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            existing = Subject.objects.filter(name__iexact=name).first()
            if existing:
                subj, created = existing, False
            else:
                subj = Subject.objects.create(name=name)
                created = True
            if created:
                messages.success(request, f'Kategoria "{name}" u shtua.')
            else:
                messages.warning(request, f'Kategoria "{subj.name}" ekziston tashmë.')
            return redirect('subject_list')
    return render(request, 'libra/subject_form.html', {'action': 'Shto Kategori'})


@login_required
def subject_edit(request, pk):
    subj = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            subj.name = name
            subj.save()
            messages.success(request, 'Kategoria u përditësua.')
            return redirect('subject_list')
    return render(request, 'libra/subject_form.html', {
        'action': 'Ndrysho Kategori', 'subject': subj
    })


@login_required
def subject_delete(request, pk):
    subj = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        name = subj.name
        subj.delete()
        messages.success(request, f'Kategoria "{name}" u fshi.')
    return redirect('subject_list')


# ── MEMBERS ───────────────────────────────────────────────────────────────────

@login_required
def member_list(request):
    q = request.GET.get('q', '').strip()
    members = Member.objects.all()
    if q:
        members = members.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(membership_number__icontains=q) |
            Q(phone__icontains=q)
        )
    return render(request, 'libra/member_list.html', {'members': members, 'q': q})


@login_required
def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    loans = member.loan_set.all().select_related('copy__book').order_by('-loan_date')
    return render(request, 'libra/member_detail.html', {'member': member, 'loans': loans})


@login_required
def member_add(request):
    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            member = form.save()
            messages.success(request, f'Anëtari "{member.full_name()}" u regjistrua.')
            return redirect('member_detail', pk=member.pk)
    else:
        last = Member.objects.order_by('-membership_date').first()
        next_num = 1
        if last:
            try:
                parts = last.membership_number.split('-')
                next_num = int(parts[-1]) + 1
            except (ValueError, IndexError):
                next_num = Member.objects.count() + 1
        form = MemberForm(initial={'membership_number': f'10-{str(next_num).zfill(4)}'})
    return render(request, 'libra/member_form.html', {'form': form, 'action': 'Regjistro Anëtar'})


@login_required
def member_edit(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if request.method == 'POST':
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, 'Të dhënat u përditësuan.')
            return redirect('member_detail', pk=member.pk)
    else:
        form = MemberForm(instance=member)
    return render(request, 'libra/member_form.html', {
        'form': form, 'action': 'Ndrysho Anëtar', 'member': member
    })


@login_required
def member_create_account(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if member.user:
        messages.warning(request, 'Ky anëtar ka tashmë llogari hyrje.')
        return redirect('member_detail', pk=pk)
    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        if len(password) < 6:
            messages.error(request, 'Fjalëkalimi duhet të ketë të paktën 6 karaktere.')
        elif User.objects.filter(username=member.membership_number).exists():
            messages.error(request, f'Username "{member.membership_number}" ekziston tashmë.')
        else:
            user = User.objects.create_user(
                username=member.membership_number,
                password=password,
                first_name=member.first_name,
                last_name=member.last_name,
                email=member.email,
            )
            member.user = user
            member.save()
            messages.success(
                request,
                f'Llogaria u krijua. Anëtari hyn me: Nr. {member.membership_number}'
            )
            return redirect('member_detail', pk=pk)
    return render(request, 'libra/member_create_account.html', {'member': member})


# ── LOANS ─────────────────────────────────────────────────────────────────────

from django.http import JsonResponse

@login_required
def author_add_ajax(request):
    if request.method == 'POST':
        last_name = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        if last_name:
            author = Author.objects.create(last_name=last_name, first_name=first_name)
            return JsonResponse({'id': author.pk, 'text': str(author)})
        return JsonResponse({'error': 'Mbiemri është i detyrueshëm'}, status=400)
    return JsonResponse({'error': 'Metodë e gabuar'}, status=405)


@login_required
def publisher_add_ajax(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        city = request.POST.get('city', '').strip()
        if name:
            pub = Publisher.objects.create(name=name, city=city)
            return JsonResponse({'id': pub.pk, 'text': str(pub)})
        return JsonResponse({'error': 'Emri është i detyrueshëm'}, status=400)
    return JsonResponse({'error': 'Metodë e gabuar'}, status=405)


def _mark_overdue():
    today = timezone.now().date()
    Loan.objects.filter(status='active', due_date__lt=today).update(status='overdue')


@login_required
def loan_list(request):
    _mark_overdue()
    status_filter = request.GET.get('status', '')
    loans = Loan.objects.all().select_related('copy__book', 'member')
    if status_filter:
        loans = loans.filter(status=status_filter)
    return render(request, 'libra/loan_list.html', {
        'loans': loans, 'status_filter': status_filter
    })


@login_required
def loan_add(request):
    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            copy = form.cleaned_data['copy']
            if not copy.is_available():
                messages.error(request, f'Kopja [{copy.copy_number}] nuk është e disponueshme.')
            else:
                loan = form.save()
                messages.success(
                    request,
                    f'U huazua: "{loan.copy.book.title}" [{loan.copy.copy_number}] → {loan.member.full_name()}'
                )
                return redirect('loan_list')
    else:
        form = LoanForm()
    return render(request, 'libra/loan_form.html', {'form': form, 'action': 'Regjistro Huazim'})


@login_required
def loan_return(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if request.method == 'POST':
        form = LoanReturnForm(request.POST, instance=loan)
        if form.is_valid():
            form.save()
            messages.success(request, f'Libri "{loan.copy.book.title}" u kthye.')
            return redirect('loan_list')
    else:
        form = LoanReturnForm(instance=loan, initial={
            'return_date': timezone.now().date(),
            'status': 'returned',
        })
    return render(request, 'libra/loan_return.html', {'form': form, 'loan': loan})


# ── QUICK OPERATIONS (desk) ───────────────────────────────────────────────────

@login_required
def quick_return(request):
    result = None
    form = QuickReturnForm()
    if request.method == 'POST':
        form = QuickReturnForm(request.POST)
        if form.is_valid():
            cn = form.cleaned_data['copy_number'].strip()
            try:
                copy = BookCopy.objects.select_related('book').get(copy_number=cn)
                loan = Loan.objects.filter(
                    copy=copy, status__in=['active', 'overdue']
                ).select_related('member').first()
                if loan:
                    today = timezone.now().date()
                    days_held = (today - loan.loan_date).days
                    days_overdue = max(0, (today - loan.due_date).days)
                    loan.status = 'returned'
                    loan.return_date = today
                    loan.save()
                    result = {
                        'success': True, 'loan': loan, 'copy': copy,
                        'days_held': days_held, 'days_overdue': days_overdue,
                    }
                    messages.success(
                        request,
                        f'✓ Libri "{copy.book.title}" u kthye nga {loan.member.full_name()}.'
                    )
                    form = QuickReturnForm()
                else:
                    result = {'success': False, 'msg': f'Kopja [{cn}] nuk ka huazim aktiv.'}
            except BookCopy.DoesNotExist:
                result = {'success': False, 'msg': f'Nuk u gjet kopja me nr. [{cn}].'}
    return render(request, 'libra/quick_return.html', {'form': form, 'result': result})


@login_required
def quick_loan(request):
    result = None
    form = QuickLoanForm()
    if request.method == 'POST':
        form = QuickLoanForm(request.POST)
        if form.is_valid():
            mn = form.cleaned_data['member_number'].strip()
            cn = form.cleaned_data['copy_number'].strip()
            days = int(form.cleaned_data['due_days'])
            errors = []
            member = copy = None
            try:
                member = Member.objects.get(membership_number=mn, is_active=True)
            except Member.DoesNotExist:
                errors.append(f'Anëtari nr. [{mn}] nuk u gjet ose është joaktiv.')
            try:
                copy = BookCopy.objects.select_related('book').get(copy_number=cn)
                if not copy.is_available():
                    errors.append(f'Kopja [{cn}] "{copy.book.title}" është tashmë e huazuar.')
            except BookCopy.DoesNotExist:
                errors.append(f'Kopja me nr. [{cn}] nuk ekziston.')
            if not errors and member and copy:
                due_date = timezone.now().date() + timezone.timedelta(days=days)
                loan = Loan.objects.create(copy=copy, member=member, due_date=due_date)
                result = {'success': True, 'loan': loan}
                messages.success(
                    request,
                    f'✓ U huazua: [{cn}] "{copy.book.title}" → {member.full_name()} (afati: {due_date})'
                )
                form = QuickLoanForm()
            else:
                for e in errors:
                    messages.error(request, e)
    return render(request, 'libra/quick_loan.html', {'form': form, 'result': result})


# ── STAFF MANAGEMENT ──────────────────────────────────────────────────────────

@login_required
def backup_download(request):
    if not request.user.is_superuser:
        messages.error(request, 'Vetëm super-admini mund të shkarkojë backup.')
        return redirect('home')
    from django.core.management import call_command
    from django.http import HttpResponse
    import io
    from datetime import datetime
    buf = io.StringIO()
    call_command('dumpdata', 'libra', indent=2, stdout=buf)
    content = buf.getvalue()
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="backup_biblioteka_{timestamp}.json"'
    return response


@login_required
def staff_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'Vetëm super-admini mund të menaxhojë stafin.')
        return redirect('home')
    staff_users = User.objects.filter(is_staff=True, is_superuser=False).order_by('username')
    return render(request, 'libra/staff_list.html', {'staff_users': staff_users})


@login_required
def staff_create(request):
    if not request.user.is_superuser:
        return redirect('home')
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            user.save()
            messages.success(request, f'Punonjësi "{user.username}" u shtua.')
            return redirect('staff_list')
    else:
        form = StaffCreateForm()
    return render(request, 'libra/staff_form.html', {'form': form})


@login_required
def staff_toggle(request, pk):
    if not request.user.is_superuser:
        return redirect('home')
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        status = 'aktivizua' if user.is_active else 'çaktivizua'
        messages.success(request, f'Llogaria "{user.username}" u {status}.')
    return redirect('staff_list')


# ── AUTH ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('home')
        try:
            return redirect('member_dashboard')
        except Exception:
            return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.is_staff:
                return redirect(request.GET.get('next', 'home'))
            try:
                _ = user.member
                return redirect('member_dashboard')
            except Exception:
                return redirect('home')
        messages.error(request, 'Nr. anëtarësie ose fjalëkalimi i gabuar.')
    return render(request, 'libra/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def change_password(request):
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Fjalëkalimi u ndryshua me sukses!')
            return redirect('member_dashboard' if not request.user.is_staff else 'home')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'libra/change_password.html', {'form': form})


# ── BARCODE SHEET GENERATOR ───────────────────────────────────────────────────

@login_required
def barcode_sheet(request):
    """Gjenero fletë me barkode të para-printuara (56/faqe, 10 faqe = 560)."""
    if not request.user.is_staff:
        messages.error(request, 'Nuk keni leje.')
        return redirect('home')

    language = request.GET.get('language', '')
    count_raw = request.GET.get('count', '560')
    try:
        count = max(1, min(int(count_raw), 560))
    except (ValueError, TypeError):
        count = 56

    if language:
        prefix = Book.LANGUAGE_PREFIX.get(language, '401')

        # Start from max(last BookCopy, last BarcodeLog) to avoid duplicates
        start_num = 1
        last_copy = BookCopy.objects.filter(
            copy_number__startswith=f'{prefix}-'
        ).order_by('-copy_number').first()
        if last_copy:
            try:
                start_num = max(start_num, int(last_copy.copy_number.split('-')[1]) + 1)
            except (ValueError, IndexError):
                pass
        last_log = BarcodeLog.objects.filter(prefix=prefix).order_by('-to_number').first()
        if last_log:
            start_num = max(start_num, last_log.to_number + 1)

        barcodes = [f"{prefix}-{str(start_num + i).zfill(5)}" for i in range(count)]
        pages = [barcodes[i:i + 56] for i in range(0, len(barcodes), 56)]

        # Log this generation
        BarcodeLog.objects.create(
            language=language,
            prefix=prefix,
            from_number=start_num,
            to_number=start_num + count - 1,
            count=count,
            generated_by=request.user,
        )

        return render(request, 'libra/barcode_sheet_print.html', {
            'pages': pages,
            'language_display': dict(Book.LANGUAGE_CHOICES).get(language, language),
            'prefix': prefix,
            'start_num': start_num,
            'count': count,
        })

    lang_choices_with_prefix = [
        (code, label, Book.LANGUAGE_PREFIX.get(code, '401'))
        for code, label in Book.LANGUAGE_CHOICES
    ]

    # Show last log per prefix for the selection form
    recent_logs = {}
    for code, _label, prefix in lang_choices_with_prefix:
        log = BarcodeLog.objects.filter(prefix=prefix).order_by('-generated_at').first()
        if log:
            recent_logs[code] = log

    return render(request, 'libra/barcode_sheet.html', {
        'lang_choices_with_prefix': lang_choices_with_prefix,
        'recent_logs': recent_logs,
    })


# ── SHELF LABEL PRINT ─────────────────────────────────────────────────────────

@login_required
def shelf_label_print(request):
    """Printo etiketa rafti (label shpine) për kopjet e librave."""
    if not request.user.is_staff:
        messages.error(request, 'Nuk keni leje.')
        return redirect('home')

    copies = BookCopy.objects.filter(
        shelf_label__gt=''
    ).select_related('book').order_by('shelf_label')

    class_filter = request.GET.get('class_prefix', '').strip()
    if class_filter:
        copies = copies.filter(shelf_label__startswith=class_filter)

    copies_list = list(copies)
    PER_PAGE = 56
    pages = [copies_list[i:i + PER_PAGE] for i in range(0, len(copies_list), PER_PAGE)]
    total = len(copies_list)
    full_pages = total // PER_PAGE
    remainder  = total % PER_PAGE

    return render(request, 'libra/shelf_label_print.html', {
        'pages': pages,
        'total': total,
        'full_pages': full_pages,
        'remainder': remainder,
        'needed': PER_PAGE - remainder if remainder else 0,
        'per_page': PER_PAGE,
        'class_filter': class_filter,
    })


# ── SUBJECT AJAX ──────────────────────────────────────────────────────────────

@login_required
def subject_search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})
    all_subs = list(Subject.objects.all())
    results  = _fuzzy_find(all_subs, lambda s: s.name, q, limit=15)
    return JsonResponse({'results': [{'id': s.pk, 'text': s.name} for s in results]})


@login_required
def subject_add_ajax(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            subject, created = Subject.objects.get_or_create(name=name)
            return JsonResponse({'id': subject.pk, 'text': subject.name, 'created': created})
        return JsonResponse({'error': 'Emri është i detyrueshëm'}, status=400)
    return JsonResponse({'error': 'Metodë e gabuar'}, status=405)


@login_required
def shelf_label_suggest(request):
    """AJAX: sugjero shelf_label bazuar në class_number."""
    class_number = request.GET.get('class_number', '').strip()
    suggestion = BookCopy.suggest_shelf_label(class_number)
    return JsonResponse({'shelf_label': suggestion})


@login_required
def next_copy_number_ajax(request):
    """AJAX: kthe numrin e ardhshëm të barkod-it për gjuhën e zgjedhur."""
    language = request.GET.get('language', 'sq')
    cn = BookCopy.next_copy_number(language=language)
    return JsonResponse({'copy_number': cn})


@login_required
def member_lookup_ajax(request):
    """AJAX: gjej anëtarin sipas membership_number — për quick_loan."""
    mn = request.GET.get('q', '').strip()
    if not mn:
        return JsonResponse({'found': False})
    try:
        member = Member.objects.get(membership_number=mn)
        overdue_count = member.loan_set.filter(status='overdue').count()
        active_count  = member.loan_set.filter(status__in=['active', 'overdue']).count()
        return JsonResponse({
            'found': True,
            'name': member.full_name(),
            'number': member.membership_number,
            'is_active': member.is_active,
            'active_loans': active_count,
            'overdue_loans': overdue_count,
        })
    except Member.DoesNotExist:
        return JsonResponse({'found': False, 'msg': f'Anëtari [{mn}] nuk u gjet.'})


@login_required
def copy_lookup_ajax(request):
    """AJAX: gjej kopjen e librit sipas copy_number — për quick_loan dhe quick_return."""
    cn = request.GET.get('q', '').strip()
    if not cn:
        return JsonResponse({'found': False})
    try:
        copy = BookCopy.objects.select_related('book').get(copy_number=cn)
        author = copy.book.primary_author()
        active_loan = Loan.objects.filter(
            copy=copy, status__in=['active', 'overdue']
        ).select_related('member').first()
        today = timezone.now().date()
        data = {
            'found': True,
            'copy_number': copy.copy_number,
            'title': copy.book.title,
            'author': str(author) if author else '',
            'shelf_label': copy.shelf_label,
            'status': copy.status,
            'available': copy.is_available(),
        }
        if active_loan:
            days_held    = (today - active_loan.loan_date).days
            days_overdue = max(0, (today - active_loan.due_date).days)
            data.update({
                'loan_member': active_loan.member.full_name(),
                'loan_member_number': active_loan.member.membership_number,
                'loan_date': str(active_loan.loan_date),
                'due_date': str(active_loan.due_date),
                'days_held': days_held,
                'days_overdue': days_overdue,
                'loan_status': active_loan.status,
            })
        return JsonResponse(data)
    except BookCopy.DoesNotExist:
        return JsonResponse({'found': False, 'msg': f'Kopja [{cn}] nuk u gjet.'})


@login_required
def mark_copy_lost(request, copy_pk):
    """Shëno kopjen si të humbur."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Nuk keni leje.'}, status=403)
    copy = get_object_or_404(BookCopy, pk=copy_pk)
    if request.method == 'POST':
        copy.status = BookCopy.STATUS_LOST
        copy.save()
        active_loan = Loan.objects.filter(
            copy=copy, status__in=['active', 'overdue']
        ).first()
        if active_loan:
            active_loan.status = 'overdue'
            active_loan.notes = (active_loan.notes or '') + ' [HUMBUR]'
            active_loan.save()
        messages.warning(
            request,
            f'Kopja [{copy.copy_number}] "{copy.book.title}" u shënua si E HUMBUR.'
        )
        return redirect(request.POST.get('next', 'loan_list'))
    return render(request, 'libra/copy_lost_confirm.html', {'copy': copy})


@login_required
def send_overdue_reminders(request):
    """Dërgo email rikujtues për të gjitha huazimet vonuara."""
    if not request.user.is_staff:
        messages.error(request, 'Nuk keni leje.')
        return redirect('home')
    if request.method != 'POST':
        return redirect('loan_list')

    from django.core.mail import send_mail
    from django.conf import settings

    _mark_overdue()
    today = timezone.now().date()
    overdue_loans = Loan.objects.filter(
        status='overdue'
    ).select_related('copy__book', 'member').order_by('member__last_name')

    sent = 0
    failed = 0
    no_email = 0

    for loan in overdue_loans:
        member = loan.member
        if not member.email:
            no_email += 1
            continue

        days_overdue = (today - loan.due_date).days
        book_title   = loan.copy.book.title
        copy_nr      = loan.copy.copy_number
        due_str      = loan.due_date.strftime('%d.%m.%Y')

        # 1-year warning vs normal reminder
        is_critical = days_overdue >= 365

        if is_critical:
            subject = f'⚠️ Biblioteka Pirok – Libër i Vonuar mbi 1 Vit / Задоцнета книга над 1 Година / Overdue Book Over 1 Year'
            body = f"""🇦🇱 SHQIP
================
I/E nderuar {member.full_name()},

Libri "{book_title}" (Nr. {copy_nr}) ka kaluar afatin e kthimit prej MBI 1 VITI ({days_overdue} ditë).
Afati i kthimit ishte: {due_str}.

Nëse libri nuk kthehet brenda 30 ditëve, biblioteka do të ndërmarrë hapat ligjorë të parashikuara
në kontratën e anëtarësisë. Do t'ju kërkohet të zëvendësoni librin dhe të paguani 1,000 denarë kostot.

Ju lutemi kontaktoni bibliotekën menjëherë.
📧 pirokbiblioteka@gmail.com
📍 Fshati Pirok, Tetovë, MK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇲🇰 МАКЕДОНСКИ
================
Почитуван/а {member.full_name()},

Книгата "{book_title}" (Бр. {copy_nr}) е задоцнета ПОВЕЌЕ ОД 1 ГОДИНА ({days_overdue} дена).
Рокот за враќање беше: {due_str}.

Доколку книгата не се врати во рок од 30 дена, библиотеката ќе преземе правни чекори
предвидени во договорот за членство. Ќе бидете обврзани да ја замените книгата и да платите 1.000 денари.

Ве молиме контактирајте ја библиотеката итно.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇬🇧 ENGLISH
===========
Dear {member.full_name()},

The book "{book_title}" (No. {copy_nr}) is OVER 1 YEAR overdue ({days_overdue} days).
The return deadline was: {due_str}.

If the book is not returned within 30 days, the library will take legal action as provided
in the membership agreement. You will be required to replace the book and pay 1,000 denars.

Please contact the library immediately.

— Biblioteka Pirok"""
        else:
            subject = f'Biblioteka Pirok – Rikujtim Kthimi / Потсетник / Return Reminder'
            body = f"""🇦🇱 SHQIP
================
I/E nderuar {member.full_name()},

Afati i kthimit të librit "{book_title}" (Nr. {copy_nr}) ka kaluar prej {days_overdue} ditësh.
Afati i kthimit ishte: {due_str}.

Ju lutemi ktheni librin sa më shpejt ose vazhdoni afatin online (maks. 2 herë) duke hyrë
në llogarinë tuaj: https://bibliotekapirok.pythonanywhere.com/hyrje/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇲🇰 МАКЕДОНСКИ
================
Почитуван/а {member.full_name()},

Рокот за враќање на книгата "{book_title}" (Бр. {copy_nr}) помина пред {days_overdue} дена.
Рокот за враќање беше: {due_str}.

Ве молиме вратете ја книгата или обновете го рокот онлајн (макс. 2 пати):
https://bibliotekapirok.pythonanywhere.com/hyrje/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🇬🇧 ENGLISH
===========
Dear {member.full_name()},

The return deadline for "{book_title}" (No. {copy_nr}) passed {days_overdue} days ago.
The deadline was: {due_str}.

Please return the book or renew your loan online (max. 2 times):
https://bibliotekapirok.pythonanywhere.com/hyrje/

— Biblioteka Pirok"""

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email],
                fail_silently=False,
            )
            sent += 1
        except Exception:
            failed += 1

    if sent:
        messages.success(request, f'✓ U dërguan {sent} email rikujtues.')
    if failed:
        messages.warning(request, f'⚠ {failed} email dështuan (kontrollo konfigurimin SMTP).')
    if no_email:
        messages.info(request, f'{no_email} anëtarë nuk kanë email të regjistruar.')
    if not overdue_loans.exists():
        messages.info(request, 'Nuk ka huazime vonuara.')

    return redirect('loan_list')


@login_required
def check_copy_number_ajax(request):
    """AJAX: kontrollo nëse copy_number ekziston tashmë (për validim real-time)."""
    copy_number = request.GET.get('copy_number', '').strip()
    if not copy_number:
        return JsonResponse({'exists': False, 'copy_number': ''})
    exists = BookCopy.objects.filter(copy_number=copy_number).exists()
    return JsonResponse({'exists': exists, 'copy_number': copy_number})


@login_required
def member_id_card(request, pk):
    """Printo kartën e anëtarit me dimensionet e kartës ID (85.6×54mm)."""
    if not request.user.is_staff:
        messages.error(request, 'Nuk keni leje.')
        return redirect('home')
    member = get_object_or_404(Member, pk=pk)
    return render(request, 'libra/member_id_card.html', {'member': member})


@login_required
def book_title_check(request):
    """AJAX: kontrollo nëse ekzistojnë libra me titull të ngjashëm."""
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({'books': []})
    books = Book.objects.filter(title__icontains=q)[:6]
    book_id = request.GET.get('book_id', '')  # kur ndryshojmë librin ekzistues
    data = []
    for b in books:
        if str(b.pk) == book_id:
            continue  # mos paralajmëro për librin që po editojmë
        data.append({
            'title': b.title,
            'author': str(b.primary_author()) if b.primary_author() else '',
            'year': b.year,
        })
    return JsonResponse({'books': data})


@login_required
def reset_numbering(request):
    """Vetëm superuseri mund të fshijë kopjet, huazimet dhe BarcodeLog-un."""
    if not request.user.is_superuser:
        messages.error(request, 'Vetëm administratori mund të aksesojë këtë faqe.')
        return redirect('home')

    def _new_code():
        alphabet = _string.ascii_uppercase + _string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(6))

    if request.method == 'POST':
        entered = request.POST.get('confirm_code', '').strip().upper()
        session_code = request.session.get('reset_confirm_code', '')
        c1 = request.POST.get('c1') == 'on'
        c2 = request.POST.get('c2') == 'on'
        c3 = request.POST.get('c3') == 'on'

        if not (c1 and c2 and c3):
            messages.error(request, 'Duhet të shënoni të gjitha tri kutitë e konfirmimit.')
        elif not entered or entered != session_code:
            messages.error(request, f'Kodi [{entered}] nuk është i saktë. Kodi duhet të përputhet saktësisht.')
        else:
            copy_count = BookCopy.objects.count()
            loan_count = Loan.objects.count()
            log_count  = BarcodeLog.objects.count()
            Loan.objects.all().delete()
            BookCopy.objects.all().delete()
            BarcodeLog.objects.all().delete()
            request.session.pop('reset_confirm_code', None)
            messages.success(
                request,
                f'Reseti u krye me sukses: {copy_count} kopje fizike, '
                f'{loan_count} huazime dhe {log_count} regjistrime barkodi u fshinë. '
                f'Numërtimi nis sëri nga 00001.'
            )
            return redirect('home')

        # Rilexo statistikat dhe gjenero kod të ri pas gabimit
        code = _new_code()
        request.session['reset_confirm_code'] = code
    else:
        code = _new_code()
        request.session['reset_confirm_code'] = code

    stats = {
        'copies': BookCopy.objects.count(),
        'loans':  Loan.objects.count(),
        'logs':   BarcodeLog.objects.count(),
    }
    return render(request, 'libra/reset_numbering.html', {'code': code, 'stats': stats})
