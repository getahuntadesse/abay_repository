# books/urls.py
from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    # Home
    path('', views.HomeView.as_view(), name='home'),
    
    # Browse
    path('browse/', views.browse_books, name='browse'),
    path('search/', views.search_books, name='search'),
    
    # Book Detail
    path('<int:book_id>/', views.book_detail, name='detail'),
    
    # Purchase
    path('<int:book_id>/purchase/', views.purchase_book, name='purchase_book'),
    path('payment/<int:purchase_id>/', views.process_payment, name='payment'),
    path('payment/success/<int:purchase_id>/', views.payment_success, name='payment_success'),
    
    # Download
    path('<int:book_id>/download/', views.download_book, name='download'),
    path('<int:book_id>/read-free/', views.read_free_book, name='read_free'),
    
    # Wishlist
    path('wishlist/', views.my_wishlist, name='my_wishlist'),
    path('<int:book_id>/wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('<int:book_id>/wishlist/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Author
    path('upload/', views.upload_book, name='upload'),
    path('my-books/', views.my_books, name='my_books'),
    path('<int:book_id>/edit/', views.edit_book, name='edit'),
    path('<int:book_id>/delete/', views.delete_book, name='delete'),
    
    # Maker
    path('pending-approval/', views.pending_approval, name='pending_approval'),
    path('<int:book_id>/publish/', views.publish_book, name='publish_book'),
    path('my-publications/', views.my_publications, name='my_publications'),
    
    # Public
    path('published/', views.published_books, name='published_books'),
    path('genre/<slug:genre_slug>/', views.genre_books, name='genre_books'),
    path('author/<int:author_id>/', views.author_books, name='author_books'),
]