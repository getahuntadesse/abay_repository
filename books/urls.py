from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    # Browse and Search
    path('', views.browse_books, name='browse'),
    path('browse/', views.browse_books, name='browse_redirect'),
    path('search/', views.search_books, name='search'),
    path('published/', views.published_books, name='published'),
    
    # Book Detail
    path('<int:book_id>/', views.book_detail, name='detail'),
    path('<int:book_id>/download/', views.download_book, name='download'),
    
    # Author Actions
    path('upload/', views.upload_book, name='upload'),
    path('my-books/', views.my_books, name='my_books'),
    path('<int:book_id>/edit/', views.edit_book, name='edit'),
    path('<int:book_id>/delete/', views.delete_book, name='delete'),
    
    # Maker Actions
    path('pending-approval/', views.pending_approval, name='pending_approval'),
    path('<int:book_id>/publish/', views.publish_book, name='publish'),
    path('my-publications/', views.my_publications, name='my_publications'),
    
    # Wishlist Actions
    path('wishlist/', views.my_wishlist, name='wishlist'),
    path('<int:book_id>/wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('<int:book_id>/wishlist/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Genre and Author
    path('genre/<slug:genre_slug>/', views.genre_books, name='genre_books'),
    path('author/<int:author_id>/', views.author_books, name='author_books'),
]