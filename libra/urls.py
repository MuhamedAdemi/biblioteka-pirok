from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('katalog/', views.catalog, name='catalog'),
    path('librat/<uuid:pk>/', views.book_detail, name='book_detail'),

    # Books (staff)
    path('librat/shto/', views.book_add, name='book_add'),
    path('librat/<uuid:pk>/ndrysho/', views.book_edit, name='book_edit'),
    path('librat/<uuid:pk>/fshi/', views.book_delete, name='book_delete'),

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

    # Loans
    path('huazime/', views.loan_list, name='loan_list'),
    path('huazime/shto/', views.loan_add, name='loan_add'),
    path('huazime/<uuid:pk>/kthe/', views.loan_return, name='loan_return'),

    # Auth
    path('hyrje/', views.login_view, name='login'),
    path('dalje/', views.logout_view, name='logout'),
]
