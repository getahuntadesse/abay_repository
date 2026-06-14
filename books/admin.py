from django.contrib import admin
from .models import Book, Genre, Wishlist

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'author', 'genre', 'price', 'status', 'downloads_count', 'created_at']
    list_filter = ['status', 'language', 'genre', 'is_free', 'created_at']
    search_fields = ['title', 'author__email', 'author__full_name', 'isbn']
    readonly_fields = ['created_at', 'updated_at', 'downloads_count', 'purchase_count', 'views_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'subtitle', 'description', 'isbn', 'author', 'genre')
        }),
        ('Publication Details', {
            'fields': ('language', 'edition', 'page_count', 'publication_year')
        }),
        ('Pricing', {
            'fields': ('price', 'is_free')
        }),
        ('Files', {
            'fields': ('file', 'cover_image', 'sample_file'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'revision_notes', 'revision_attempts')
        }),
        ('Statistics', {
            'fields': ('downloads_count', 'purchase_count', 'views_count', 'avg_rating', 'total_reviews'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('submitted_for_review_at', 'checker_reviewed_at', 'maker_approved_at', 
                      'published_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.submitted_for_review_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'slug', 'is_active', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['is_active']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'book', 'created_at']
    search_fields = ['client__email', 'book__title']
    list_filter = ['created_at']