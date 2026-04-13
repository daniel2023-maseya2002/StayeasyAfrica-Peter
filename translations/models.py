# translations/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class TranslatedText(models.Model):
    """
    Model for caching translated text to avoid repeated API calls.
    """
    
    original_text = models.TextField(
        _("original text"),
        help_text=_("The original text before translation")
    )
    
    language = models.CharField(
        _("language"),
        max_length=10,
        help_text=_("Target language code (e.g., 'fr', 'sw')")
    )
    
    translated_text = models.TextField(
        _("translated text"),
        help_text=_("The translated text")
    )
    
    source_language = models.CharField(
        _("source language"),
        max_length=10,
        default='en',
        help_text=_("Source language code (default: 'en')")
    )
    
    created_at = models.DateTimeField(
        _("created at"),
        default=timezone.now,
        editable=False
    )
    
    updated_at = models.DateTimeField(
        _("updated at"),
        auto_now=True
    )
    
    usage_count = models.IntegerField(
        _("usage count"),
        default=0,
        help_text=_("Number of times this translation has been used")
    )
    
    class Meta:
        verbose_name = _("translated text")
        verbose_name_plural = _("translated texts")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['original_text', 'language']),
            models.Index(fields=['language', '-created_at']),
        ]
        unique_together = [['original_text', 'language', 'source_language']]
    
    def __str__(self):
        preview = self.original_text[:50]
        return f"Translation '{preview}...' from {self.source_language} to {self.language}"
    
    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])