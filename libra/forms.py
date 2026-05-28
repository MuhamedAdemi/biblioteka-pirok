from django import forms
from django.forms import inlineformset_factory
from .models import Book, BookAuthor, Author, Publisher, Member, Loan, Subject


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
            'title', 'subtitle', 'isbn', 'publisher', 'year',
            'format', 'pages', 'class_number', 'quantity',
            'general_note', 'contents_note', 'summary', 'subjects',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control'}),
            'publisher': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 1999'}),
            'format': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 24 cm'}),
            'pages': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. vi, 283 f.'}),
            'class_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'p.sh. 330.952'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
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
        fields = ['book', 'member', 'due_date', 'notes']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-select'}),
            'member': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class LoanReturnForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['return_date', 'status', 'notes']
        widgets = {
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kërko libra, autorë, ISBN...',
        })
    )
