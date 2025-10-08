"""
Rutas/Endpoints del sistema Manual AI
"""

# Las rutas se registran automáticamente al importarse
from ai_mode_projects.routes import health
from ai_mode_projects.routes import projects
from ai_mode_projects.routes import keywords
from ai_mode_projects.routes import analysis
from ai_mode_projects.routes import results
from ai_mode_projects.routes import competitors
from ai_mode_projects.routes import exports

__all__ = [
    'health',
    'projects',
    'keywords',
    'analysis',
    'results',
    'competitors',
    'exports'
]

