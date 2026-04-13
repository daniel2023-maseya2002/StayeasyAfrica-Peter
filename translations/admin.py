# translations/admin.py
from django.contrib import admin
from .models import TranslatedText


@admin.register(TranslatedText)
class TranslatedTextAdmin(admin.ModelAdmin):
    list_display = ['id', 'language', 'source_language', 'original_text_preview', 'translated_text_preview', 'usage_count', 'created_at']
    list_filter = ['language', 'source_language', 'created_at']
    search_fields = ['original_text', 'translated_text']
    readonly_fields = ['created_at', 'updated_at', 'usage_count']
    
    def original_text_preview(self, obj):
        return obj.original_text[:50] + '...' if len(obj.original_text) > 50 else obj.original_text
    original_text_preview.short_description = 'Original Text'
    
    def translated_text_preview(self, obj):
        return obj.translated_text[:50] + '...' if len(obj.translated_text) > 50 else obj.translated_text
    translated_text_preview.short_description = 'Translated Text'