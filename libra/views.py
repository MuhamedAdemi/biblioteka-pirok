from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from .models import Book, Author, Publisher, Member, Loan, Subject, BookAuthor
from .forms import (
    BookForm, BookAuthorFormSet, MemberForm, LoanForm,
    LoanReturnForm, SearchForm, AuthorForm, PublisherForm,
)


# ── PUBLIC VIEWS ──────────────────────────────────────────────────────────────

def home(request):
    recent_books = Book.objects.all().order_by('-created')[:8]
    total_books = Book.objects.count()
    total_members = Member.objects.filter(is_active=True).count()
    active_loans = Loan.objects.filter(status='active').count()
    context = {
        'recent_books': recent_books,
        'total_books': total_books,
        'total_members': total_members,
        'active_loans': active_loans,
    }
    return render(request, 'libra/home.html', context)


def catalog(request):
    form = SearchForm(request.GET)
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
    context = {
        'books': books,
        'form': form,
        'q': q,
        'subjects': subjects,
        'subject_filter': subject_filter,
    }
    return render(request, 'libra/catalog.html', context)


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    primary_authors = book.book_authors.filter(role='primary').select_related('author')
    secondary_authors = book.book_authors.exclude(role='primary').select_related('author')
    context = {
        'book': book,
        'primary_authors': primary_authors,
        'secondary_authors': secondary_authors,
    }
    return render(request, 'libra/book_detail.html', context)


# ── BOOK MANAGEMENT (staff only) ─────────────────────────────────────────────

@login_required
def book_add(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        formset = BookAuthorFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            book = form.save()
            formset.instance = book
            formset.save()
            messages.success(request, f'Libri "{book.title}" u shtua me sukses.')
            return redirect('book_detail', pk=book.pk)
    else:
        form = BookForm()
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


# ── AUTHOR MANAGEMENT ────────────────────────────────────────────────────────

@login_required
def author_list(request):
    authors = Author.objects.all()
    return render(request, 'libra/author_list.html', {'authors': authors})


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
            messages.success(request, f'Autori "{author}" u përditësua.')
            return redirect('author_list')
    else:
        form = AuthorForm(instance=author)
    return render(request, 'libra/author_form.html', {'form': form, 'action': 'Ndrysho Autor', 'author': author})


# ── PUBLISHER MANAGEMENT ─────────────────────────────────────────────────────

@login_required
def publisher_list(request):
    publishers = Publisher.objects.all()
    return render(request, 'libra/publisher_list.html', {'publishers': publishers})


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


# ── MEMBER MANAGEMENT ────────────────────────────────────────────────────────

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
    loans = member.loan_set.all().select_related('book').order_by('-loan_date')
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
        # auto-generate next membership number
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


# ── LOAN MANAGEMENT ──────────────────────────────────────────────────────────

@login_required
def loan_list(request):
    status_filter = request.GET.get('status', '')
    loans = Loan.objects.all().select_related('book', 'member')
    if status_filter:
        loans = loans.filter(status=status_filter)
    # auto-mark overdue
    today = timezone.now().date()
    Loan.objects.filter(status='active', due_date__lt=today).update(status='overdue')
    loans = loans.select_related('book', 'member')
    return render(request, 'libra/loan_list.html', {
        'loans': loans, 'status_filter': status_filter
    })


@login_required
def loan_add(request):
    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            book = form.cleaned_data['book']
            if book.available_copies() <= 0:
                messages.error(request, f'Libri "{book.title}" nuk ka kopje të disponueshme.')
            else:
                loan = form.save()
                messages.success(request, f'Huazimi u regjistrua: "{loan.book.title}" → {loan.member.full_name()}')
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
            messages.success(request, f'Libri "{loan.book.title}" u kthye.')
            return redirect('loan_list')
    else:
        form = LoanReturnForm(instance=loan, initial={
            'return_date': timezone.now().date(),
            'status': 'returned',
        })
    return render(request, 'libra/loan_return.html', {'form': form, 'loan': loan})


# ── AUTH ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'home'))
        messages.error(request, 'Emri i përdoruesit ose fjalëkalimi i gabuar.')
    return render(request, 'libra/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')
