from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('katalog/', views.catalog, name='catalog'),
    path('rreth-nesh/', views.about, name='about'),
    path('librat/<uuid:pk>/', views.book_detail, name='book_detail'),

    # Books (staff)
    path('librat/shto/', views.book_add, name='book_add'),
    path('librat/<uuid:pk>/ndrysho/', views.book_edit, name='book_edit'),
    path('librat/<uuid:pk>/fshi/', views.book_delete, name='book_delete'),

    # Book copies
    path('librat/<uuid:pk>/kopje/', views.book_copy_list, name='book_copy_list'),
    path('librat/<uuid:pk>/kopje/shto/', views.book_copy_add, name='book_copy_add'),
    path('kopje/<int:copy_pk>/fshi/', views.book_copy_delete, name='book_copy_delete'),

    # AJAX
    path('ajax/autor-shto/', views.author_add_ajax, name='author_add_ajax'),
    path('ajax/botues-shto/', views.publisher_add_ajax, name='publisher_add_ajax'),
    path('ajax/autor-kerko/', views.author_search, name='author_search'),
    path('ajax/botues-kerko/', views.publisher_search, name='publisher_search'),

    # ISBN check (hapi i parë para regjistrimit)
    path('librat/isbn/', views.book_isbn_check, name='book_isbn_check'),

    # Authors
    path('autore/', views.author_list, name='author_list'),
    path('autore/shto/', views.author_add, name='author_add'),
    path('autore/<int:pk>/ndrysho/', views.author_edit, name='author_edit'),

    # Publishers
    path('botues/', views.publisher_list, name='publisher_list'),
    path('botues/shto/', views.publisher_add, name='publisher_add'),

    # Members
    path('anetaret/', views.member_list, name='member_list'),
    path('anetaret/shto/', views.member_add, name='member_add'),
    path('anetaret/<uuid:pk>/', views.member_detail, name='member_detail'),
    path('anetaret/<uuid:pk>/ndrysho/', views.member_edit, name='member_edit'),
    path('anetaret/<uuid:pk>/llogari/', views.member_create_account, name='member_create_account'),

    # Loans
    path('huazime/', views.loan_list, name='loan_list'),
    path('huazime/shto/', views.loan_add, name='loan_add'),
    path('huazime/<uuid:pk>/kthe/', views.loan_return, name='loan_return'),
    path('huazime/<uuid:pk>/vazhdo/', views.loan_renew, name='loan_renew'),

    # Quick desk operations
    path('kthe/', views.quick_return, name='quick_return'),
    path('huazo/', views.quick_loan, name='quick_loan'),

    # Staff management (superuser only)
    path('stafi/', views.staff_list, name='staff_list'),
    path('stafi/shto/', views.staff_create, name='staff_create'),
    path('stafi/<int:pk>/toggle/', views.staff_toggle, name='staff_toggle'),

    # Member dashboard
    path('dashboard/', views.member_dashboard, name='member_dashboard'),

    # Contact
    path('kontakt/', views.contact, name='contact'),

    # Auth
    path('hyrje/', views.login_view, name='login'),
    path('dalje/', views.logout_view, name='logout'),
    path('ndrysho-fjalekalimin/', views.change_password, name='change_password'),
]
