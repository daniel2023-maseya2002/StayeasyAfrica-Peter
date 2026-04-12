# stayease/utils/translation_service.py
import requests
import logging
import json

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Translation service using MyMemory API (free, no API key required).
    """
    
    @classmethod
    def translate_text(cls, text, target_lang, source_lang='en'):
        """
        Translate text using MyMemory API.
        """
        if not text or not target_lang or target_lang == source_lang:
            return text
        
        # Map language codes for MyMemory
        # MyMemory uses 2-letter codes mostly
        lang_map = {
            'en': 'en', 'fr': 'fr', 'sw': 'sw', 'es': 'es', 'de': 'de',
            'it': 'it', 'pt': 'pt', 'ru': 'ru', 'zh': 'zh', 'ja': 'ja',
            'ko': 'ko', 'ar': 'ar', 'hi': 'hi', 'nl': 'nl', 'pl': 'pl'
        }
        
        source = lang_map.get(source_lang, 'en')
        target = lang_map.get(target_lang, target_lang)
        
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
                
                # Clean up HTML entities
                translated = translated.replace('&#39;', "'").replace('&quot;', '"')
                translated = translated.replace('&amp;', '&')
                
                # Remove the " - MyMemory" suffix if present
                if ' - MyMemory' in translated:
                    translated = translated.replace(' - MyMemory', '')
                
                # Check if translation is different from original
                if translated and translated != text:
                    logger.info(f"Translation successful: {source_lang} -> {target_lang}")
                    return translated
                else:
                    logger.warning("Translation returned same as original")
                    return text
            else:
                logger.warning(f"MyMemory API error: {response.status_code}")
                return text
                
        except requests.exceptions.Timeout:
            logger.warning("MyMemory API timeout")
            return text
        except requests.exceptions.ConnectionError:
            logger.warning("MyMemory API connection error")
            return text
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {str(e)}")
            return text
        except Exception as e:
            logger.warning(f"Translation error: {str(e)}")
            return text