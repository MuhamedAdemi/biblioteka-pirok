from django.contrib import admin
from .models import Book, BookAuthor, BookCopy, Author, Publisher, Subject, Member, Loan


class BookAuthorInline(admin.TabularInline):
    model = BookAuthor
    extra = 2
    autocomplete_fields = ['author']


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 1
    readonly_fields = ['copy_number']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'primary_author', 'publisher', 'year', 'isbn', 'class_number', 'total_copies']
    list_filter = ['year', 'publisher', 'subjects']
    search_fields = ['title', 'subtitle', 'isbn', 'class_number',
                     'book_authors__author__last_name']
    inlines = [BookAuthorInline, BookCopyInline]
    filter_horizontal = ['subjects']
    fieldsets = (
        (None, {'fields': ('title', 'subtitle', 'isbn', 'class_number')}),
        ('Publikimi', {'fields': ('publisher', 'year', 'format', 'pages')}),
        ('Shënime', {'fields': ('general_note', 'contents_note', 'summary')}),
        ('Kategoritë', {'fields': ('subjects',)}),
    )


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ['copy_number', 'book', 'is_available', 'notes']
    search_fields = ['copy_number', 'book__title']
    autocomplete_fields = ['book']


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name']
    search_fields = ['last_name', 'first_name']


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'country']
    search_fields = ['name', 'city']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['membership_number', 'last_name', 'first_name', 'phone', 'membership_date', 'is_active']
    list_filter = ['is_active', 'membership_date']
    search_fields = ['first_name', 'last_name', 'membership_number', 'phone', 'email']


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'member', 'loan_date', 'due_date', 'status', 'renewals_count']
    list_filter = ['status', 'loan_date']
    search_fields = ['copy__book__title', 'member__last_name', 'member__first_name', 'copy__copy_number']
    autocomplete_fields = ['copy', 'member']
