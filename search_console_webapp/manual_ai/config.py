"""
Configuración y constantes del sistema Manual AI
"""

# Costes en RUs
MANUAL_AI_KEYWORD_ANALYSIS_COST = 1

# Límites del sistema
MAX_KEYWORDS_PER_PROJECT = 200
MAX_COMPETITORS_PER_PROJECT = 4
MAX_NOTE_LENGTH = 500

# Configuración de análisis
DEFAULT_DAYS_RANGE = 30
DEFAULT_TOP_DOMAINS_LIMIT = 10

# Tipos de eventos
EVENT_TYPES = {
    'PROJECT_CREATED': 'project_created',
    'PROJECT_UPDATED': 'project_updated',
    'PROJECT_DELETED': 'project_deleted',
    'KEYWORDS_ADDED': 'keywords_added',
    'KEYWORD_DELETED': 'keyword_deleted',
    'KEYWORD_UPDATED': 'keyword_updated',
    'MANUAL_ANALYSIS_COMPLETED': 'manual_analysis_completed',
    'MANUAL_ANALYSIS_QUOTA_EXCEEDED': 'manual_analysis_quota_exceeded',
    'DAILY_ANALYSIS': 'daily_analysis',
    'COMPETITORS_CHANGED': 'competitors_changed',
    'COMPETITORS_UPDATED': 'competitors_updated',
    'MANUAL_NOTE_ADDED': 'manual_note_added'
}

# Configuración de cron
CRON_LOCK_CLASS_ID = 4242

