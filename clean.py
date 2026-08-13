import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute('SHOW TABLES;')
    tables = [row[0] for row in cursor.fetchall()]
    
    prefixes = ['books_', 'payments_', 'reviews_', 'purchases', 'quality_reviews', 'payment_']
    exact = ['books', 'genres', 'wishlists', 'book_versions', 'book_reviews', 
            'book_activity_logs', 'review_assignments', 'checker_reviews', 
            'revision_requests', 'editorial_decisions', 'publication_records', 
            'book_notifications', 'email_events', 'author_responses', 
            'bookmarks', 'reading_history', 'reading_progress']
    
    to_drop = []
    for t in tables:
        if any(t.startswith(p) for p in prefixes) or t in exact:
            to_drop.append(t)
            
    cursor.execute('SET FOREIGN_KEY_CHECKS = 0;')
    for t in to_drop:
        cursor.execute(f'DROP TABLE IF EXISTS {t};')
        print('Dropped', t)
        
    cursor.execute("DELETE FROM django_migrations WHERE app IN ('books', 'payments', 'reviews');")
    cursor.execute('SET FOREIGN_KEY_CHECKS = 1;')
    print('Cleaned up db')
