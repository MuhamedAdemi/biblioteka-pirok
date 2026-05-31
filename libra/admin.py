from django.contrib import admin
from .models import Book, BookAuthor, BookCopy, Author, Publisher, Subject, Member, Loan


class SuperuserDeleteMixin:
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class BookAuthorInline(admin.TabularInline):
    model = BookAuthor
    extra = 2
    autocomplete_fields = ['author']


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 1
    fields = ['copy_number', 'shelf_label', 'notes']


@admin.register(Book)
class BookAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ['title', 'primary_author', 'publisher', 'year', 'isbn', 'class_number', 'total_copies']
    list_filter = ['year', 'publisher', 'subjects', 'language']
    search_fields = ['title', 'subtitle', 'isbn', 'class_number',
                     'book_authors__author__last_name']
    inlines = [BookAuthorInline, BookCopyInline]
    filter_horizontal = ['subjects']
    fieldsets = (
        (None, {'fields': ('title', 'subtitle', 'language', 'isbn', 'class_number')}),
        ('Publikimi', {'fields': ('publisher', 'year', 'format', 'pages')}),
        ('Shënime', {'fields': ('general_note', 'contents_note', 'summary')}),
        ('Kategoritë', {'fields': ('subjects',)}),
    )


@admin.register(BookCopy)
class BookCopyAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ['copy_number', 'shelf_label', 'book', 'is_available', 'notes']
    search_fields = ['copy_number', 'shelf_label', 'book__title']
    autocomplete_fields = ['book']


@admin.register(Author)
class AuthorAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ['last_name', 'first_name']
    search_fields = ['last_name', 'first_name']


@admin.register(Publisher)
class PublisherAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ['name', 'city', 'country']
    search_fields = ['name', 'city']


@admin.register(Subject)
class SubjectAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Member)
class MemberAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ['membership_number', 'last_name', 'first_name', 'phone', 'membership_date', 'is_active']
    list_filter = ['is_active', 'membership_date']
    search_fields = ['first_name', 'last_name', 'membership_number', 'phone', 'email']


@admin.register(Loan)
class LoanAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ['__str__', 'member', 'loan_date', 'due_date', 'status', 'renewals_count']
    list_filter = ['status', 'loan_date']
    search_fields = ['copy__book__title', 'member__last_name', 'member__first_name', 'copy__copy_number']
    autocomplete_fields = ['copy', 'member']
