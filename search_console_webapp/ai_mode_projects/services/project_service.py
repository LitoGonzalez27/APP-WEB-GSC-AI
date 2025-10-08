"""
Servicio de lógica de negocio para proyectos AI Mode
"""

import logging
from typing import List, Dict, Optional
from ai_mode_projects.models.project_repository import ProjectRepository
from ai_mode_projects.models.event_repository import EventRepository
from ai_mode_projects.config import EVENT_TYPES, MAX_KEYWORDS_PER_PROJECT

logger = logging.getLogger(__name__)


class ProjectService:
    """Servicio para gestión de proyectos AI Mode"""
    
    def __init__(self):
        self.project_repo = ProjectRepository()
        self.event_repo = EventRepository()
    
    def get_user_projects(self, user_id: int) -> List[Dict]:
        """
        Obtener todos los proyectos de un usuario con estadísticas
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Lista de proyectos
        """
        return self.project_repo.get_user_projects(user_id)
    
    def get_project_details(self, project_id: int, user_id: int) -> Optional[Dict]:
        """
        Obtener detalles de un proyecto
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario (para validación)
            
        Returns:
            Dict con detalles del proyecto o None
        """
        # Validar pertenencia
        if not self.project_repo.user_owns_project(user_id, project_id):
            logger.warning(f"User {user_id} attempted to access project {project_id} without permission")
            return None
        
        return self.project_repo.get_project_with_details(project_id)
    
    def create_project(self, user_id: int, name: str, description: str, 
                      brand_name: str, country_code: str) -> Dict:
        """
        Crear un nuevo proyecto AI Mode
        
        Args:
            user_id: ID del usuario
            name: Nombre del proyecto
            description: Descripción
            brand_name: Nombre de la marca a monitorizar
            country_code: Código de país
            
        Returns:
            Dict con resultado de la creación
        """
        try:
            # Validaciones
            if not name or not brand_name:
                return {'success': False, 'error': 'Name and brand name are required'}
            
            # Crear proyecto
            project_id = self.project_repo.create_project(
                user_id=user_id,
                name=name,
                description=description,
                brand_name=brand_name,
                country_code=country_code
            )
            
            # Crear evento
            self.event_repo.create_event(
                project_id=project_id,
                event_type=EVENT_TYPES['PROJECT_CREATED'],
                event_title=f'AI Mode project "{name}" created',
                user_id=user_id
            )
            
            return {
                'success': True,
                'project_id': project_id,
                'message': 'AI Mode project created successfully'
            }
            
        except Exception as e:
            logger.error(f"Error creating AI Mode project: {e}")
            return {'success': False, 'error': str(e)}
    
    def update_project(self, project_id: int, user_id: int, name: str, description: str) -> Dict:
        """
        Actualizar un proyecto
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            name: Nuevo nombre
            description: Nueva descripción
            
        Returns:
            Dict con resultado de la actualización
        """
        try:
            # Validar pertenencia
            if not self.project_repo.user_owns_project(user_id, project_id):
                return {'success': False, 'error': 'Unauthorized'}
            
            # Validar datos
            if not name or not name.strip():
                return {'success': False, 'error': 'Project name cannot be empty'}
            
            # Actualizar
            success = self.project_repo.update_project(project_id, user_id, name.strip(), description.strip())
            
            if not success:
                return {'success': False, 'error': 'Project name already exists'}
            
            return {'success': True, 'message': 'Project updated successfully'}
            
        except Exception as e:
            logger.error(f"Error updating project {project_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_project(self, project_id: int, user_id: int) -> Dict:
        """
        Eliminar un proyecto y todos sus datos
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            
        Returns:
            Dict con resultado de la eliminación
        """
        logger.info(f"Delete request for project {project_id} by user {user_id}")
        
        # Validar pertenencia
        if not self.project_repo.user_owns_project(user_id, project_id):
            logger.warning(f"Unauthorized delete attempt for project {project_id} by user {user_id}")
            return {'success': False, 'error': 'Unauthorized'}
        
        # Eliminar proyecto
        return self.project_repo.delete_project(project_id, user_id)
    
    def user_owns_project(self, user_id: int, project_id: int) -> bool:
        """
        Verificar si un usuario es propietario de un proyecto
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            
        Returns:
            True si es propietario
        """
        return self.project_repo.user_owns_project(user_id, project_id)

