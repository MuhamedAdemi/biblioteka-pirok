from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from .models import Book, Author, Publisher, Member, Loan, Subject, BookAuthor, BookCopy
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
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'biblioteka.pirok@gmail.com'),
                    recipient_list=[getattr(settings, 'CONTACT_EMAIL', 'biblioteka.pirok@gmail.com')],
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
def author_search(request):
    q = request.GET.get('q', '').strip()
    authors = Author.objects.filter(
        Q(last_name__icontains=q) | Q(first_name__icontains=q)
    )[:10]
    data = [{'id': a.pk, 'text': str(a)} for a in authors]
    return JsonResponse({'results': data})


@login_required
def publisher_search(request):
    q = request.GET.get('q', '').strip()
    pubs = Publisher.objects.filter(name__icontains=q)[:10]
    data = [{'id': p.pk, 'text': str(p)} for p in pubs]
    return JsonResponse({'results': data})


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
        'form': form, 'formset': formset, 'action': 'Shto Libër'
    })


@login_required
def book_edit(request, pk):
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
    return render(request, 'libra/book_form.html', {
        'form': form, 'formset': formset, 'action': 'Ndrysho Libër', 'book': book
    })


@login_required
def book_delete(request, pk):
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


@login_required
def book_copy_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookCopyForm(request.POST)
        if form.is_valid():
            copy = form.save(commit=False)
            copy.book = book
            copy.save()
            messages.success(request, f'Kopja [{copy.copy_number}] u shtua.')
            return redirect('book_copy_list', pk=pk)
    else:
        form = BookCopyForm(initial={
            'copy_number': BookCopy.next_copy_number(language=book.language),
            'shelf_label': BookCopy.suggest_shelf_label(book.class_number),
        })
    return render(request, 'libra/book_copy_form.html', {'form': form, 'book': book})


@login_required
def book_copy_delete(request, copy_pk):
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
    authors = Author.objects.all()
    if q:
        authors = authors.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q)
        )
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
    publishers = Publisher.objects.all()
    if q:
        publishers = publishers.filter(
            Q(name__icontains=q) | Q(city__icontains=q)
        )
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
                next_num = int(last.membership_number) + 1
            except ValueError:
                next_num = Member.objects.count() + 1
        form = MemberForm(initial={'membership_number': str(next_num).zfill(4)})
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
            cn = form.cleaned_data['copy_number'].strip().zfill(4)
            try:
                copy = BookCopy.objects.select_related('book').get(copy_number=cn)
                loan = Loan.objects.filter(
                    copy=copy, status__in=['active', 'overdue']
                ).select_related('member').first()
                if loan:
                    loan.status = 'returned'
                    loan.return_date = timezone.now().date()
                    loan.save()
                    result = {'success': True, 'loan': loan, 'copy': copy}
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
            mn = form.cleaned_data['member_number'].strip().zfill(4)
            cn = form.cleaned_data['copy_number'].strip().zfill(4)
            days = form.cleaned_data['due_days']
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
