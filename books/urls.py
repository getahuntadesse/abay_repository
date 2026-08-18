# books/urls.py
from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    # ============================================
    # BROWSE & SEARCH
    # ============================================
    path('browse/', views.browse_books, name='browse'),
    path('search/', views.search_books, name='search'),
    
    # ============================================
    # BOOK DETAIL
    # ============================================
    path('<int:book_id>/', views.book_detail, name='detail'),
    
    # ============================================
    # PURCHASE & PAYMENT
    # ============================================
    path('<int:book_id>/purchase/', views.purchase_book, name='purchase_book'),
    path('payment/<int:purchase_id>/', views.process_payment, name='payment'),
    path('payment/success/<int:purchase_id>/', views.payment_success, name='payment_success'),
    
    # ============================================
    # DOWNLOAD & READING
    # ============================================
    path('<int:book_id>/download/', views.download_book, name='download'),  # blocked → reader
    path('<int:book_id>/read/', views.read_book, name='read'),
    path('<int:book_id>/content/', views.stream_book_content, name='content'),
    path('<int:book_id>/read-free/', views.read_free_book, name='read_free'),
    
    # ============================================
    # TELEBIRR PAYMENT CALLBACKS
    # ============================================
    path('telebirr/callback/', views.telebirr_callback, name='telebirr_callback'),
    path('telebirr/return/', views.telebirr_return, name='telebirr_return'),
    # path('telebirr/simulate/<str:transaction_id>/', views.telebirr_simulate, name='telebirr_simulate'),  # disabled
    # path('telebirr/pay/<str:transaction_id>/', views.telebirr_pay_simulate, name='telebirr_pay_simulate'),  # disabled
    path('telebirr/process/<str:transaction_id>/', views.telebirr_pay_process, name='telebirr_pay_process'),
    
    # ============================================
    # USER'S BOOKS (MY LIBRARY)
    # ============================================
    path('my-books/', views.my_books_user, name='my_books'),
    path('my-books/user/', views.my_books_user, name='my_books_user'),
    path('my-books/author/', views.my_books_author, name='my_books_author'),
    
    # ============================================
    # WISHLIST
    # ============================================
    path('wishlist/', views.my_wishlist, name='my_wishlist'),
    path('<int:book_id>/wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('<int:book_id>/wishlist/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # ============================================
    # AUTHOR URLS
    # ============================================
    path('upload/', views.upload_book, name='upload'),
    path('submit/<int:book_id>/', views.submit_book, name='submit_book'),
    path('<int:book_id>/edit/', views.edit_book, name='edit'),
    path('<int:book_id>/delete/', views.delete_book, name='delete'),
    path('author/revision/<int:book_id>/', views.author_revision_submit, name='author_revision_submit'),
    path('author/dashboard/', views.author_dashboard, name='author_dashboard'),
    
    # ============================================
    # MAKER URLS
    # ============================================
    path('maker/dashboard/', views.maker_dashboard, name='maker_dashboard'),
    path('maker/initial-review/<int:book_id>/', views.maker_initial_review, name='maker_initial_review'),
    path('maker/assign-checker/<int:book_id>/', views.maker_assign_checker, name='maker_assign_checker'),
    path('maker/review-decision/<int:book_id>/', views.maker_review_decision, name='maker_review_decision'),
    path('maker/pending-publication/', views.maker_pending_publication, name='maker_pending_publication'),
    path('maker/publish/<int:book_id>/', views.maker_publish_book, name='maker_publish_book'),
    path('maker/reject/<int:book_id>/', views.maker_reject_book, name='maker_reject_book'),
    path('maker/pending-approval/', views.pending_approval, name='pending_approval'),
    path('maker/publications/', views.my_publications, name='my_publications'),
    
    # ============================================
    # CHECKER URLS
    # ============================================
    path('checker/dashboard/', views.checker_dashboard, name='checker_dashboard'),
    path('checker/accept/<int:assignment_id>/', views.checker_accept_assignment, name='checker_accept_assignment'),
    path('checker/decline/<int:assignment_id>/', views.checker_decline_assignment, name='checker_decline_assignment'),
    path('checker/conflict/<int:assignment_id>/', views.checker_conflict_assignment, name='checker_conflict_assignment'),
    path('checker/submit-review/<int:assignment_id>/', views.checker_submit_review, name='checker_submit_review'),
    path('checker/process-review/', views.process_checker_review, name='process_checker_review'),
    path('checker/view/<int:book_id>/', views.view_book_for_review, name='view_book_for_review'),
    
    # ============================================
    # ADMIN URLS
    # ============================================
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # ============================================
    # PUBLIC URLS
    # ============================================
    path('published/', views.published_books, name='published_books'),
    path('genre/<slug:genre_slug>/', views.genre_books, name='genre_books'),
    path('author/<int:author_id>/', views.author_books, name='author_books'),
]