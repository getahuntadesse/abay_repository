from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('submit-checker/', views.submit_checker_review, name='submit_checker_review'),
    path('submit-maker/', views.submit_maker_review, name='submit_maker_review'),
    path('book/<int:book_id>/', views.book_reviews, name='book_reviews'),
]