from django.contrib import admin
from .models import QualityReview

@admin.register(QualityReview)
class QualityReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'reviewer', 'review_type', 'overall_score', 'recommendation', 'created_at']
    list_filter = ['review_type', 'recommendation', 'created_at']
    search_fields = ['book__title', 'reviewer__email', 'comments']
    readonly_fields = ['created_at', 'updated_at', 'overall_score']
    
    fieldsets = (
        ('Review Information', {
            'fields': ('book', 'reviewer', 'review_type')
        }),
        ('Quality Scores', {
            'fields': ('content_quality', 'editorial_quality', 'technical_quality', 'overall_score')
        }),
        ('Decision', {
            'fields': ('recommendation', 'comments')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Calculate overall score if all three scores exist
        if obj.content_quality and obj.editorial_quality and obj.technical_quality:
            obj.overall_score = (obj.content_quality + obj.editorial_quality + obj.technical_quality) / 3
        super().save_model(request, obj, form, change)