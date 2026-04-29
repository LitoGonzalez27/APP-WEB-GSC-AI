"""
Servicio de lógica de negocio para proyectos
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from flask import has_request_context, request
from manual_ai.models.project_repository import ProjectRepository
from manual_ai.models.event_repository import EventRepository
from manual_ai.config import EVENT_TYPES, MAX_KEYWORDS_PER_PROJECT
from services.utils import normalize_search_console_url

logger = logging.getLogger(__name__)


class ProjectService:
    """Servicio para gestión de proyectos"""
    
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
        # Validar acceso de lectura (owner o colaborador)
        if not self.project_repo.user_has_project_access(user_id, project_id):
            logger.warning(f"User {user_id} attempted to access project {project_id} without permission")
            return None

        project = self.project_repo.get_project_with_details(project_id)
        if project:
            is_owner = project.get('user_id') == user_id
            project['access_role'] = 'owner' if is_owner else 'viewer'
            project['is_owner'] = is_owner
            project['can_edit'] = is_owner
            project['can_manage_access'] = is_owner
        return project
    
    def create_project(self, user_id: int, name: str, description: str, 
                      domain: str, country_code: str, competitors: List[str] = None) -> Dict:
        """
        Crear un nuevo proyecto
        
        Args:
            user_id: ID del usuario
            name: Nombre del proyecto
            description: Descripción
            domain: Dominio del proyecto
            country_code: Código de país
            competitors: Lista de competidores
            
        Returns:
            Dict con resultado de la creación
        """
        try:
            # Validaciones
            if not name or not domain:
                return {'success': False, 'error': 'Name and domain are required'}
            
            # Crear proyecto
            project_id = self.project_repo.create_project(
                user_id=user_id,
                name=name,
                description=description,
                domain=domain,
                country_code=country_code,
                competitors=competitors
            )
            
            # Crear evento
            self.event_repo.create_event(
                project_id=project_id,
                event_type=EVENT_TYPES['PROJECT_CREATED'],
                event_title=f'Project "{name}" created',
                user_id=user_id
            )
            
            return {
                'success': True,
                'project_id': project_id,
                'message': 'Project created successfully'
            }
            
        except Exception as e:
            logger.error(f"Error creating project: {e}")
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
        Eliminar un proyecto y todos sus datos. Solo se permite si el proyecto
        está previamente pausado (is_active=false), siguiendo el mismo patrón
        que LLM Monitoring para evitar borrados accidentales.
        """
        logger.info(f"Delete request for project {project_id} by user {user_id}")

        # Validar pertenencia
        if not self.project_repo.user_owns_project(user_id, project_id):
            logger.warning(f"Unauthorized delete attempt for project {project_id} by user {user_id}")
            return {'success': False, 'error': 'Unauthorized'}

        # Exigir pausa previa
        status = self.project_repo.get_project_status(project_id)
        if not status:
            return {'success': False, 'error': 'Project not found'}
        if status.get('is_active'):
            return {
                'success': False,
                'error': 'Cannot delete an active project. Please pause it first.',
                'action_required': 'deactivate_first'
            }

        # Eliminar proyecto
        return self.project_repo.delete_project(project_id, user_id)

    def pause_project(self, project_id: int, user_id: int) -> Dict:
        """Pausa manualmente un proyecto: deja de consumir cuota pero conserva
        todos sus datos. Sólo el owner puede pausar.
        """
        if not self.project_repo.user_owns_project(user_id, project_id):
            return {'success': False, 'error': 'Unauthorized'}

        row = self.project_repo.pause_project(project_id)
        if not row:
            return {'success': False, 'error': 'Project not found or already paused'}

        try:
            self.event_repo.create_event(
                project_id=project_id,
                event_type='project_paused',
                event_title=f'Project "{row["name"]}" paused manually',
                user_id=user_id
            )
        except Exception as evt_exc:
            logger.warning(f"Could not log pause event for project {project_id}: {evt_exc}")

        return {
            'success': True,
            'project_id': row['id'],
            'project_name': row['name'],
            'message': f'Project "{row["name"]}" paused. It will no longer run in automatic analyses.'
        }

    def resume_project(self, project_id: int, user_id: int) -> Dict:
        """Reactiva un proyecto pausado.

        Antes de reactivar, valida que el usuario tenga cuota disponible.
        Si no la tiene, devuelve un error con la fecha de renovación.
        """
        if not self.project_repo.user_owns_project(user_id, project_id):
            return {'success': False, 'error': 'Unauthorized'}

        # Validar cuota antes de reactivar — si está sin cuota, no permitir.
        try:
            from quota_manager import get_user_quota_status
            quota = get_user_quota_status(user_id) or {}
        except Exception as quota_exc:
            logger.warning(f"Quota status unavailable for user {user_id}: {quota_exc}")
            quota = {}

        if quota and not quota.get('can_consume', True):
            reset_date = quota.get('reset_date')
            return {
                'success': False,
                'error': 'quota_exceeded',
                'message': 'You have used all your monthly quota. The project will be available to resume after your plan renews.',
                'quota_info': {
                    'plan': quota.get('plan'),
                    'quota_used': quota.get('quota_used'),
                    'quota_limit': quota.get('quota_limit'),
                    'remaining': quota.get('remaining'),
                },
                'reset_date': reset_date.isoformat() if hasattr(reset_date, 'isoformat') else reset_date,
            }

        row = self.project_repo.resume_project(project_id)
        if not row:
            return {'success': False, 'error': 'Project not found or already active'}

        try:
            self.event_repo.create_event(
                project_id=project_id,
                event_type='project_resumed',
                event_title=f'Project "{row["name"]}" reactivated',
                user_id=user_id
            )
        except Exception as evt_exc:
            logger.warning(f"Could not log resume event for project {project_id}: {evt_exc}")

        return {
            'success': True,
            'project_id': row['id'],
            'project_name': row['name'],
            'message': f'Project "{row["name"]}" reactivated. It will be included in upcoming automatic analyses.'
        }
    
    def user_owns_project(self, user_id: int, project_id: int) -> bool:
        """
        Verificar acceso al proyecto.
        - En peticiones GET: owner o colaborador viewer
        - En peticiones no-GET: solo owner
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            
        Returns:
            True si tiene acceso según el contexto
        """
        if has_request_context() and request.method == 'GET':
            return self.project_repo.user_has_project_access(user_id, project_id)
        return self.project_repo.user_owns_project(user_id, project_id)

    def user_can_view_project(self, user_id: int, project_id: int) -> bool:
        return self.project_repo.user_has_project_access(user_id, project_id)
