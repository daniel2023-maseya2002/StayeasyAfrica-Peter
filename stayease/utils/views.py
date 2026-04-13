# stayease/utils/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .translation_service import TranslationService


class TranslateView(APIView):
    """
    API endpoint for translating text with database caching.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        text = request.data.get('text', '').strip()
        target_lang = request.data.get('target_lang', '').strip().lower()
        source_lang = request.data.get('source_lang', 'en').strip().lower()
        
        if not text:
            return Response(
                {'error': 'Text is required for translation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not target_lang:
            return Response(
                {'error': 'Target language is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if target_lang == source_lang:
            return Response({
                'translated_text': text,
                'original_text': text,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'cached': False
            }, status=status.HTTP_200_OK)
        
        translated_text = TranslationService.translate_text(
            text=text,
            target_lang=target_lang,
            source_lang=source_lang
        )
        
        return Response({
            'translated_text': translated_text,
            'original_text': text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'cached': translated_text != text
        }, status=status.HTTP_200_OK)