from django.db import models
from accounts.models import CustomUser

class Notification(models.Model):
    TYPE_CHOICES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.URLField(blank=True, default='')
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_read']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def mark_as_read(self):
        self.is_read = True
        self.save()