# stayease/utils/translation_service.py
import requests
import logging
import json
import hashlib
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Translation service using MyMemory API with database caching.
    """
    
    @classmethod
    def _get_cache_key(cls, text, target_lang, source_lang='en'):
        """Generate a cache key for the translation."""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"translation_{source_lang}_{target_lang}_{text_hash}"
    
    @classmethod
    def _get_from_database(cls, text, target_lang, source_lang='en'):
        """Retrieve translation from database if it exists."""
        try:
            from translations.models import TranslatedText
            translation = TranslatedText.objects.get(
                original_text=text,
                language=target_lang,
                source_language=source_lang
            )
            translation.increment_usage()
            logger.info(f"Database cache hit for translation: {source_lang} -> {target_lang}")
            return translation.translated_text
        except Exception as e:
            logger.info(f"Database cache miss: {str(e)}")
            return None
    
    @classmethod
    def _save_to_database(cls, text, target_lang, translated_text, source_lang='en'):
        """Save translation to database."""
        try:
            from translations.models import TranslatedText
            translation, created = TranslatedText.objects.get_or_create(
                original_text=text,
                language=target_lang,
                source_language=source_lang,
                defaults={
                    'translated_text': translated_text
                }
            )
            if not created:
                translation.translated_text = translated_text
                translation.save()
            logger.info(f"Translation saved to database: {source_lang} -> {target_lang}")
            return True
        except Exception as e:
            logger.error(f"Failed to save translation to database: {str(e)}")
            return False
    
    @classmethod
    def translate_text(cls, text, target_lang, source_lang='en'):
        """
        Translate text using MyMemory API with database caching.
        """
        if not text or not target_lang or target_lang == source_lang:
            return text
        
        lang_map = {
            'en': 'en', 'fr': 'fr', 'sw': 'sw', 'es': 'es', 'de': 'de',
            'it': 'it', 'pt': 'pt', 'ru': 'ru', 'zh': 'zh', 'ja': 'ja',
            'ko': 'ko', 'ar': 'ar', 'hi': 'hi', 'nl': 'nl', 'pl': 'pl'
        }
        
        source = lang_map.get(source_lang, 'en')
        target = lang_map.get(target_lang, target_lang)
        
        # STEP 1: Try to get from database first
        cached_translation = cls._get_from_database(text, target_lang, source_lang)
        if cached_translation:
            return cached_translation
        
        # STEP 2: Try to get from memory cache
        cache_key = cls._get_cache_key(text, target_lang, source_lang)
        memory_cached = cache.get(cache_key)
        if memory_cached:
            logger.info(f"Memory cache hit for translation: {source_lang} -> {target_lang}")
            cls._save_to_database(text, target_lang, memory_cached, source_lang)
            return memory_cached
        
        # STEP 3: Call external API
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text,
                'langpair': f"{source}|{target}",
                'de': 'stayease@example.com'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                translated = data.get('responseData', {}).get('translatedText', text)
                
                translated = translated.replace('&#39;', "'").replace('&quot;', '"')
                translated = translated.replace('&amp;', '&')
                
                if ' - MyMemory' in translated:
                    translated = translated.replace(' - MyMemory', '')
                
                if translated and translated != text:
                    logger.info(f"Translation successful: {source_lang} -> {target_lang}")
                    
                    cls._save_to_database(text, target_lang, translated, source_lang)
                    cache.set(cache_key, translated, timeout=60 * 60 * 24 * 30)
                    
                    return translated
                else:
                    logger.warning("Translation returned same as original")
                    return text
            else:
                logger.warning(f"MyMemory API error: {response.status_code}")
                return text
                
        except Exception as e:
            logger.warning(f"Translation error: {str(e)}")
            return text