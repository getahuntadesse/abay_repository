# initial_data.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import CustomUser, AuthorProfile
from books.models import Genre

# Create genres
genres = [
    'Fiction', 'Non-Fiction', 'Technology', 'History', 
    'Literature', 'Poetry', 'Children', 'Education',
    'Business', 'Self-Help', 'Science', 'Religion'
]

for genre_name in genres:
    Genre.objects.get_or_create(
        name=genre_name,
        slug=genre_name.lower().replace(' ', '-')
    )
    print(f"Created genre: {genre_name}")

print("Initial data created successfully!")