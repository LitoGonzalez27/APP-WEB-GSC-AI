"""
Rutas/Endpoints del sistema Manual AI
"""

# Las rutas se registran automáticamente al importarse
from manual_ai.routes import health
from manual_ai.routes import projects
from manual_ai.routes import keywords
from manual_ai.routes import analysis
from manual_ai.routes import results
from manual_ai.routes import competitors
from manual_ai.routes import exports

__all__ = [
    'health',
    'projects',
    'keywords',
    'analysis',
    'results',
    'competitors',
    'exports'
]

