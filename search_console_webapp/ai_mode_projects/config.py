"""
Configuración y constantes del sistema AI Mode Monitoring
"""

# Costes en RUs (AI Mode puede ser más costoso que Manual AI)
AI_MODE_KEYWORD_ANALYSIS_COST = 2

# Límites del sistema
MAX_KEYWORDS_PER_PROJECT = 100
MAX_COMPETITORS_PER_PROJECT = 10  # AI Mode: Fuentes/medios citados (TechCrunch, Forbes, etc.)
MAX_NOTE_LENGTH = 500

# Configuración de análisis
DEFAULT_DAYS_RANGE = 30

# Tipos de eventos
EVENT_TYPES = {
    'PROJECT_CREATED': 'project_created',
    'PROJECT_UPDATED': 'project_updated',
    'PROJECT_DELETED': 'project_deleted',
    'KEYWORDS_ADDED': 'keywords_added',
    'KEYWORD_DELETED': 'keyword_deleted',
    'KEYWORD_UPDATED': 'keyword_updated',
    'AI_MODE_ANALYSIS_COMPLETED': 'ai_mode_analysis_completed',
    'AI_MODE_ANALYSIS_QUOTA_EXCEEDED': 'ai_mode_analysis_quota_exceeded',
    'DAILY_ANALYSIS': 'daily_analysis',
    'MANUAL_NOTE_ADDED': 'manual_note_added',
    'BRAND_MENTIONED': 'brand_mentioned',
    'BRAND_NOT_MENTIONED': 'brand_not_mentioned'
}

# Configuración de cron (diferente del manual_ai para evitar conflictos)
CRON_LOCK_CLASS_ID = 4243

# Configuración de SerpApi AI Mode
SERPAPI_AI_MODE_ENGINE = 'google'
SERPAPI_AI_MODE_TYPE = 'ai_mode'

