# core/file_handlers.py
import os
import magic
from django.core.exceptions import ValidationError
from django.core.files.uploadhandler import FileUploadHandler
from django.conf import settings
import hashlib

class SecureFileUploadHandler(FileUploadHandler):
    """Secure file upload handler with validation"""
    
    def __init__(self, request=None):
        super().__init__(request)
        self.content_type = None
        self.file_size = 0
        self.temp_file = None
    
    def receive_data_chunk(self, raw_data, start):
        self.file_size += len(raw_data)
        
        # Check file size limit
        if self.file_size > settings.MAX_UPLOAD_SIZE:
            raise ValidationError(f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB")
        
        # Store first chunk for MIME type detection
        if start == 0:
            self.first_chunk = raw_data[:1024]
        
        return raw_data
    
    def file_complete(self, file_size):
        # Validate file type using magic
        if hasattr(self, 'first_chunk'):
            mime = magic.from_buffer(self.first_chunk, mime=True)
            if mime not in settings.ALLOWED_UPLOAD_MIME_TYPES:
                raise ValidationError(f"File type '{mime}' is not allowed.")
        
        # Validate file extension
        if hasattr(self, 'filename'):
            ext = os.path.splitext(self.filename)[1].lower()
            if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
                raise ValidationError(f"File extension '{ext}' is not allowed.")
        
        return self.temp_file

class FileValidator:
    @staticmethod
    def validate_file(file_obj):
        """Validate uploaded file for security"""
        
        # Check file size
        if file_obj.size > settings.MAX_UPLOAD_SIZE:
            raise ValidationError(f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB")
        
        # Check MIME type
        try:
            mime = magic.from_buffer(file_obj.read(1024), mime=True)
            if mime not in settings.ALLOWED_UPLOAD_MIME_TYPES:
                raise ValidationError(f"File type '{mime}' is not allowed.")
        except Exception:
            raise ValidationError("Unable to validate file type.")
        
        # Check for malicious content (simple check)
        file_obj.seek(0)
        content = file_obj.read(4096)
        
        # Check for common malicious patterns
        malicious_patterns = [
            b'<?php', b'eval(', b'base64_decode', b'system(',
            b'exec(', b'shell_exec(', b'passthru(', b'popen('
        ]
        
        for pattern in malicious_patterns:
            if pattern in content.lower():
                raise ValidationError("File contains potentially malicious content.")
        
        # Generate file hash for verification
        file_hash = hashlib.sha256(file_obj.read()).hexdigest()
        
        # Reset file pointer
        file_obj.seek(0)
        
        return {
            'size': file_obj.size,
            'mime_type': mime,
            'hash': file_hash
        }

    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent directory traversal"""
        import re
        
        # Remove path separators
        filename = filename.replace('/', '').replace('\\', '')
        
        # Remove dangerous characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        
        return filename