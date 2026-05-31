from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Book, BookAuthor, BookCopy, Author, Publisher, Member, Loan, Subject


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['last_name', 'first_name']
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mbiemri'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emri'}),
        }


class PublisherForm(forms.ModelForm):
    class Meta:
        model = Publisher
        fields = ['name', 'city', 'country']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
        }


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 'subtitle', 'language', 'isbn', 'publisher', 'year',
            'format', 'pages', 'class_number',
            'general_note', 'contents_note', 'summary', 'subjects',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control'}),
            'publisher': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 1999'}),
            'format': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 24 cm'}),
            'pages': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. vi, 283 f.'}),
            'class_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 330.952'}),
            'general_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contents_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'subjects': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
        }


BookAuthorFormSet = inlineformset_factory(
    Book, BookAuthor,
    fields=['author', 'role', 'order'],
    extra=3,
    can_delete=True,
    widgets={
        'author': forms.Select(attrs={'class': 'form-select'}),
        'role': forms.Select(attrs={'class': 'form-select'}),
        'order': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:70px'}),
    }
)


class BookCopyForm(forms.ModelForm):
    class Meta:
        model = BookCopy
        fields = ['copy_number', 'shelf_label', 'notes']
        widgets = {
            'copy_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 101-000001'}),
            'shelf_label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 3-00001'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Shënime opsionale'}),
        }


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'address', 'membership_number', 'is_active', 'notes',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'membership_number': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['copy', 'member', 'due_date', 'notes']
        widgets = {
            'copy': forms.Select(attrs={'class': 'form-select'}),
            'member': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_ids = [
            c.pk for c in BookCopy.objects.select_related('book')
            if c.is_available()
        ]
        self.fields['copy'].queryset = BookCopy.objects.filter(
            pk__in=available_ids
        ).select_related('book').order_by('copy_number')
        self.fields['member'].queryset = Member.objects.filter(is_active=True)


class LoanReturnForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['return_date', 'status', 'notes']
        widgets = {
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class QuickReturnForm(forms.Form):
    copy_number = forms.CharField(
        max_length=8,
        label="Nr. i Kopjes (Barkod)",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '0001',
            'autofocus': True,
            'style': 'font-size:2rem; letter-spacing:.3rem; max-width:200px',
        })
    )


class QuickLoanForm(forms.Form):
    member_number = forms.CharField(
        max_length=8,
        label="Nr. i Anëtarit",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '0001',
            'style': 'font-size:1.5rem; letter-spacing:.2rem',
        })
    )
    copy_number = forms.CharField(
        max_length=8,
        label="Nr. i Kopjes (Barkod)",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '0001',
            'style': 'font-size:1.5rem; letter-spacing:.2rem',
        })
    )
    due_days = forms.IntegerField(
        initial=14,
        min_value=1,
        max_value=90,
        label="Afati (ditë)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'value': 14})
    )


class StaffCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'


class SearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kërko libra, autorë, ISBN...',
        })
    )
