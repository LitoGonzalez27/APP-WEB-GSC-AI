"""
Servicio para gestión de competidores en proyectos
"""

import logging
import json
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection
from services.utils import normalize_search_console_url
from manual_ai.config import MAX_COMPETITORS_PER_PROJECT

logger = logging.getLogger(__name__)


class _ValidationMixin:

    @staticmethod
    def validate_competitors(competitors: List[str], project_domain: str) -> Dict:
        """
        Validar y normalizar lista de competidores
        
        Args:
            competitors: Lista de dominios competidores
            project_domain: Dominio del proyecto (para excluir)
            
        Returns:
            Dict con competidores validados y errores
        """
        if not isinstance(competitors, list):
            return {
                'success': False,
                'error': 'Competitors must be a list',
                'validated': []
            }
        
        if len(competitors) > MAX_COMPETITORS_PER_PROJECT:
            return {
                'success': False,
                'error': f'Maximum {MAX_COMPETITORS_PER_PROJECT} competitors allowed',
                'validated': []
            }
        
        # Normalizar dominio del proyecto
        normalized_project_domain = normalize_search_console_url(project_domain) or project_domain.lower()
        
        # Validar y normalizar competidores
        validated_competitors = []
        errors = []
        
        for competitor in competitors:
            if not competitor or not isinstance(competitor, str):
                continue
            
            # Normalizar dominio
            normalized = normalize_search_console_url(competitor.strip())
            if not normalized:
                errors.append(f'Invalid domain: {competitor}')
                continue
            
            # No permitir el dominio del proyecto como competidor
            if normalized == normalized_project_domain:
                continue
            
            # Evitar duplicados
            if normalized not in validated_competitors:
                validated_competitors.append(normalized)
        
        return {
            'success': True,
            'validated': validated_competitors,
            'errors': errors if errors else None
        }
