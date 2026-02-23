"""
Project access control service.

This module adds project-level collaboration without changing existing billing/plan logic.
Owners keep full control; invited users get view-only access by default.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import psycopg2

from database import get_db_connection, get_user_by_email, get_user_by_id
from email_service import send_email

logger = logging.getLogger(__name__)

MODULE_CONFIG = {
    "llm_monitoring": {
        "table": "llm_monitoring_projects",
        "label": "LLM Monitoring",
        "path": "/llm-monitoring",
    },
    "manual_ai": {
        "table": "manual_ai_projects",
        "label": "AI Overview Monitoring",
        "path": "/manual-ai/",
    },
    "ai_mode": {
        "table": "ai_mode_projects",
        "label": "AI Mode Monitoring",
        "path": "/ai-mode-projects/",
    },
}

ALLOWED_ROLES = {"viewer"}
ALLOWED_INVITATION_STATUSES = {"pending", "accepted", "revoked", "expired"}
INVITATION_EXPIRY_DAYS = int(os.getenv("PROJECT_INVITATION_EXPIRY_DAYS", "7"))
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_supported_module(module_name: str) -> bool:
    return module_name in MODULE_CONFIG


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_missing_table_error(exc: Exception) -> bool:
    if isinstance(exc, psycopg2.errors.UndefinedTable):
        return True
    message = str(exc).lower()
    return (
        "project_collaborators" in message
        or "project_invitations" in message
    )


def get_module_label(module_name: str) -> str:
    return MODULE_CONFIG.get(module_name, {}).get("label", module_name)


def get_module_path(module_name: str) -> str:
    return MODULE_CONFIG.get(module_name, {}).get("path", "/dashboard")


def get_project_owner(module_name: str, project_id: int) -> Optional[Dict]:
    """Return project owner info (project id, owner id, project name)."""
    if not _is_supported_module(module_name):
        return None

    table = MODULE_CONFIG[module_name]["table"]
    conn = get_db_connection()
    if not conn:
        return None

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, user_id, name
            FROM {table}
            WHERE id = %s
            """,
            (project_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error(
            "Error resolving project owner for %s:%s - %s",
            module_name,
            project_id,
            exc,
        )
        return None
    finally:
        if cur:
            cur.close()
        conn.close()


def user_is_project_owner(user_id: int, module_name: str, project_id: int) -> bool:
    owner = get_project_owner(module_name, project_id)
    return bool(owner and owner.get("user_id") == user_id)


def _get_membership_role(user_id: int, module_name: str, project_id: int) -> Optional[str]:
    conn = get_db_connection()
    if not conn:
        return None

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role
            FROM project_collaborators
            WHERE module_name = %s
              AND project_id = %s
              AND user_id = %s
            """,
            (module_name, project_id, user_id),
        )
        row = cur.fetchone()
        return row.get("role") if row else None
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        logger.error(
            "Error reading collaborator role for user=%s module=%s project=%s: %s",
            user_id,
            module_name,
            project_id,
            exc,
        )
        return None
    finally:
        if cur:
            cur.close()
        conn.close()


def user_can_view_project(user_id: int, module_name: str, project_id: int) -> bool:
    if not _is_supported_module(module_name):
        return False

    if user_is_project_owner(user_id, module_name, project_id):
        return True

    role = _get_membership_role(user_id, module_name, project_id)
    return role in ALLOWED_ROLES


def user_can_edit_project(user_id: int, module_name: str, project_id: int) -> bool:
    """Current safe policy: only owner can edit/delete/configure."""
    return user_is_project_owner(user_id, module_name, project_id)


def user_can_manage_project_access(user_id: int, module_name: str, project_id: int) -> bool:
    return user_is_project_owner(user_id, module_name, project_id)


def user_has_any_module_access(user_id: int, module_name: str) -> bool:
    """True when user has at least one shared project in a module."""
    if not _is_supported_module(module_name):
        return False

    conn = get_db_connection()
    if not conn:
        return False

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM project_collaborators c
            WHERE c.user_id = %s
              AND c.module_name = %s
            LIMIT 1
            """,
            (user_id, module_name),
        )
        return cur.fetchone() is not None
    except Exception as exc:
        if _is_missing_table_error(exc):
            return False
        logger.error(
            "Error checking module shared access for user=%s module=%s: %s",
            user_id,
            module_name,
            exc,
        )
        return False
    finally:
        if cur:
            cur.close()
        conn.close()


def get_project_permissions(user_id: int, module_name: str, project_id: int) -> Dict:
    if user_is_project_owner(user_id, module_name, project_id):
        return {
            "access_role": "owner",
            "is_owner": True,
            "can_view": True,
            "can_edit": True,
            "can_manage_access": True,
        }

    role = _get_membership_role(user_id, module_name, project_id)
    if role:
        return {
            "access_role": role,
            "is_owner": False,
            "can_view": True,
            "can_edit": False,
            "can_manage_access": False,
        }

    return {
        "access_role": None,
        "is_owner": False,
        "can_view": False,
        "can_edit": False,
        "can_manage_access": False,
    }


def list_project_members(module_name: str, project_id: int) -> List[Dict]:
    owner = get_project_owner(module_name, project_id)
    if not owner:
        return []

    members: List[Dict] = []
    owner_user = get_user_by_id(owner["user_id"])
    if owner_user:
        members.append(
            {
                "user_id": owner_user["id"],
                "name": owner_user.get("name") or owner_user.get("email"),
                "email": owner_user.get("email"),
                "role": "owner",
                "is_owner": True,
                "joined_at": None,
            }
        )

    conn = get_db_connection()
    if not conn:
        return members

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                c.user_id,
                c.role,
                c.created_at,
                u.name,
                u.email
            FROM project_collaborators c
            JOIN users u ON u.id = c.user_id
            WHERE c.module_name = %s
              AND c.project_id = %s
            ORDER BY c.created_at DESC
            """,
            (module_name, project_id),
        )
        for row in cur.fetchall() or []:
            members.append(
                {
                    "user_id": row["user_id"],
                    "name": row.get("name") or row.get("email"),
                    "email": row.get("email"),
                    "role": row.get("role") or "viewer",
                    "is_owner": False,
                    "joined_at": row["created_at"].isoformat() if row.get("created_at") else None,
                }
            )
    except Exception as exc:
        if not _is_missing_table_error(exc):
            logger.error(
                "Error listing members for module=%s project=%s: %s",
                module_name,
                project_id,
                exc,
            )
    finally:
        if cur:
            cur.close()
        conn.close()

    return members


def list_project_invitations(module_name: str, project_id: int) -> List[Dict]:
    conn = get_db_connection()
    if not conn:
        return []

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                invitee_email,
                invitee_name,
                role,
                status,
                expires_at,
                created_at,
                accepted_at
            FROM project_invitations
            WHERE module_name = %s
              AND project_id = %s
            ORDER BY created_at DESC
            """,
            (module_name, project_id),
        )
        rows = cur.fetchall() or []
        invitations = []
        now = datetime.utcnow()
        for row in rows:
            status = row.get("status")
            expires_at = row.get("expires_at")
            if status == "pending" and expires_at and expires_at.replace(tzinfo=None) < now:
                status = "expired"
            invitations.append(
                {
                    "id": row["id"],
                    "invitee_email": row.get("invitee_email"),
                    "invitee_name": row.get("invitee_name"),
                    "role": row.get("role") or "viewer",
                    "status": status,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                    "accepted_at": row["accepted_at"].isoformat() if row.get("accepted_at") else None,
                }
            )
        return invitations
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        logger.error(
            "Error listing invitations for module=%s project=%s: %s",
            module_name,
            project_id,
            exc,
        )
        return []
    finally:
        if cur:
            cur.close()
        conn.close()


def _build_invitation_link(raw_token: str) -> str:
    base_url = os.getenv("PUBLIC_BASE_URL", "https://app.clicandseo.com").rstrip("/")
    return f"{base_url}/project-invitations/accept?token={raw_token}"


def _send_project_invitation_email(
    to_email: str,
    to_name: Optional[str],
    inviter_name: str,
    project_name: str,
    module_name: str,
    invitation_link: str,
) -> bool:
    display_name = to_name or to_email.split("@")[0]
    module_label = get_module_label(module_name)
    subject = f"Invitation to {project_name} on ClicandSEO"

    html_body = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
      <meta charset=\"UTF-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
      <title>Project Invitation</title>
    </head>
    <body style=\"font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;\">
      <div style=\"max-width:640px; margin:0 auto; background:#fff; border-radius:10px; padding:28px;\">
        <h2 style=\"margin-top:0; color:#161616;\">You've been invited to a project</h2>
        <p>Hi {display_name},</p>
        <p><strong>{inviter_name}</strong> invited you to view the project <strong>{project_name}</strong> in <strong>{module_label}</strong>.</p>
        <p>This invitation grants <strong>view-only</strong> access to that project.</p>
        <p style=\"margin: 24px 0;\">
          <a href=\"{invitation_link}\" style=\"background:#D8F9B8; color:#161616; text-decoration:none; padding:12px 18px; border-radius:8px; font-weight:600;\">Accept Invitation</a>
        </p>
        <p>If the button doesn't work, open this link in your browser:</p>
        <p style=\"word-break:break-all;\">{invitation_link}</p>
        <p style=\"color:#6b7280; font-size:13px; margin-top:20px;\">This invitation expires in {INVITATION_EXPIRY_DAYS} days.</p>
      </div>
    </body>
    </html>
    """

    text_body = (
        f"Hi {display_name},\n\n"
        f"{inviter_name} invited you to view project '{project_name}' in {module_label}.\n"
        f"Access is view-only.\n\n"
        f"Accept invitation: {invitation_link}\n\n"
        f"This invitation expires in {INVITATION_EXPIRY_DAYS} days.\n"
    )

    return send_email(to_email, subject, html_body, text_body)


def create_project_invitation(
    module_name: str,
    project_id: int,
    inviter_user_id: int,
    invitee_email: str,
    invitee_name: Optional[str] = None,
    role: str = "viewer",
) -> Tuple[bool, Dict]:
    if not _is_supported_module(module_name):
        return False, {"error": "Unsupported module"}

    normalized_email = (invitee_email or "").strip().lower()
    if not normalized_email:
        return False, {"error": "Invitee email is required"}
    if not EMAIL_PATTERN.match(normalized_email):
        return False, {"error": "Invitee email is invalid"}

    if role not in ALLOWED_ROLES:
        return False, {"error": "Unsupported role"}

    owner = get_project_owner(module_name, project_id)
    if not owner:
        return False, {"error": "Project not found"}

    if owner["user_id"] != inviter_user_id:
        return False, {"error": "Only project owner can invite users"}

    inviter = get_user_by_id(inviter_user_id)
    if not inviter:
        return False, {"error": "Inviter user not found"}

    if inviter.get("email", "").lower() == normalized_email:
        return False, {"error": "You already own this project"}

    existing_user = get_user_by_email(normalized_email)
    if existing_user and user_can_view_project(existing_user["id"], module_name, project_id):
        return False, {"error": "This user already has access to the project"}

    raw_token = secrets.token_urlsafe(32)
    token_hash = _token_hash(raw_token)
    expires_at = datetime.utcnow() + timedelta(days=INVITATION_EXPIRY_DAYS)

    conn = get_db_connection()
    if not conn:
        return False, {"error": "Database connection error"}

    cur = None
    try:
        cur = conn.cursor()

        # Revoke any pending invitation for the same email/project before creating a new one.
        cur.execute(
            """
            UPDATE project_invitations
            SET status = 'revoked', updated_at = NOW()
            WHERE module_name = %s
              AND project_id = %s
              AND lower(invitee_email) = lower(%s)
              AND status = 'pending'
            """,
            (module_name, project_id, normalized_email),
        )

        cur.execute(
            """
            INSERT INTO project_invitations (
                module_name,
                project_id,
                owner_user_id,
                inviter_user_id,
                invitee_email,
                invitee_name,
                role,
                token_hash,
                status,
                expires_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW(), NOW())
            RETURNING id, created_at
            """,
            (
                module_name,
                project_id,
                owner["user_id"],
                inviter_user_id,
                normalized_email,
                (invitee_name or "").strip() or None,
                role,
                token_hash,
                expires_at,
            ),
        )

        inserted = cur.fetchone()
        conn.commit()

        invitation_link = _build_invitation_link(raw_token)
        email_sent = False
        try:
            email_sent = _send_project_invitation_email(
                to_email=normalized_email,
                to_name=(invitee_name or "").strip() or None,
                inviter_name=inviter.get("name") or inviter.get("email") or "ClicandSEO",
                project_name=owner.get("name") or f"Project {project_id}",
                module_name=module_name,
                invitation_link=invitation_link,
            )
        except Exception as email_exc:
            logger.error(
                "Invitation created but email delivery failed for module=%s project=%s email=%s: %s",
                module_name,
                project_id,
                normalized_email,
                email_exc,
            )
            email_sent = False

        return True, {
            "invitation": {
                "id": inserted["id"],
                "invitee_email": normalized_email,
                "invitee_name": (invitee_name or "").strip() or None,
                "role": role,
                "status": "pending",
                "expires_at": expires_at.isoformat(),
                "created_at": inserted["created_at"].isoformat() if inserted.get("created_at") else None,
            },
            "email_sent": email_sent,
        }

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return False, {"error": "Project access tables are not initialized yet"}
        logger.error(
            "Error creating invitation module=%s project=%s inviter=%s: %s",
            module_name,
            project_id,
            inviter_user_id,
            exc,
        )
        return False, {"error": "Could not create invitation"}
    finally:
        if cur:
            cur.close()
        conn.close()


def accept_project_invitation(token: str, user_id: int) -> Tuple[bool, Dict]:
    raw_token = (token or "").strip()
    if not raw_token:
        return False, {"error": "Missing invitation token"}

    user = get_user_by_id(user_id)
    if not user:
        return False, {"error": "User not found"}

    conn = get_db_connection()
    if not conn:
        return False, {"error": "Database connection error"}

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM project_invitations
            WHERE token_hash = %s
            LIMIT 1
            """,
            (_token_hash(raw_token),),
        )
        invitation = cur.fetchone()
        if not invitation:
            return False, {"error": "Invitation not found"}

        status = invitation.get("status")
        if status != "pending":
            return False, {"error": f"Invitation is {status}"}

        expires_at = invitation.get("expires_at")
        if expires_at and expires_at.replace(tzinfo=None) < datetime.utcnow():
            cur.execute(
                """
                UPDATE project_invitations
                SET status = 'expired', updated_at = NOW()
                WHERE id = %s
                """,
                (invitation["id"],),
            )
            conn.commit()
            return False, {"error": "Invitation has expired"}

        invitation_email = (invitation.get("invitee_email") or "").strip().lower()
        current_email = (user.get("email") or "").strip().lower()
        if invitation_email != current_email:
            return False, {
                "error": "Invitation email does not match your current account",
                "expected_email": invitation_email,
                "current_email": current_email,
            }

        module_name = invitation.get("module_name")
        project_id = invitation.get("project_id")
        owner = get_project_owner(module_name, project_id)
        if not owner:
            return False, {"error": "Project no longer exists"}

        role = invitation.get("role") or "viewer"
        if role not in ALLOWED_ROLES:
            role = "viewer"

        cur.execute(
            """
            INSERT INTO project_collaborators (
                module_name,
                project_id,
                owner_user_id,
                user_id,
                role,
                invited_by_user_id,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (module_name, project_id, user_id)
            DO UPDATE SET
                role = EXCLUDED.role,
                owner_user_id = EXCLUDED.owner_user_id,
                invited_by_user_id = EXCLUDED.invited_by_user_id,
                updated_at = NOW()
            """,
            (
                module_name,
                project_id,
                owner["user_id"],
                user_id,
                role,
                invitation.get("inviter_user_id"),
            ),
        )

        cur.execute(
            """
            UPDATE project_invitations
            SET status = 'accepted',
                accepted_by_user_id = %s,
                accepted_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (user_id, invitation["id"]),
        )

        conn.commit()

        permissions = get_project_permissions(user_id, module_name, project_id)
        return True, {
            "module_name": module_name,
            "module_label": get_module_label(module_name),
            "project_id": project_id,
            "project_name": owner.get("name") or f"Project {project_id}",
            "permissions": permissions,
            "redirect_path": get_module_path(module_name),
        }

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return False, {"error": "Project access tables are not initialized yet"}
        logger.error("Error accepting invitation user=%s: %s", user_id, exc)
        return False, {"error": "Could not accept invitation"}
    finally:
        if cur:
            cur.close()
        conn.close()


def revoke_project_invitation(invitation_id: int, requester_user_id: int) -> Tuple[bool, Dict]:
    conn = get_db_connection()
    if not conn:
        return False, {"error": "Database connection error"}

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM project_invitations WHERE id = %s", (invitation_id,))
        invitation = cur.fetchone()
        if not invitation:
            return False, {"error": "Invitation not found"}

        if invitation.get("owner_user_id") != requester_user_id:
            return False, {"error": "Only the project owner can revoke invitations"}

        if invitation.get("status") != "pending":
            return False, {"error": "Only pending invitations can be revoked"}

        cur.execute(
            """
            UPDATE project_invitations
            SET status = 'revoked', updated_at = NOW()
            WHERE id = %s
            """,
            (invitation_id,),
        )
        conn.commit()
        return True, {"message": "Invitation revoked"}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return False, {"error": "Project access tables are not initialized yet"}
        logger.error("Error revoking invitation %s: %s", invitation_id, exc)
        return False, {"error": "Could not revoke invitation"}
    finally:
        if cur:
            cur.close()
        conn.close()


def remove_project_member(
    module_name: str,
    project_id: int,
    member_user_id: int,
    requester_user_id: int,
) -> Tuple[bool, Dict]:
    owner = get_project_owner(module_name, project_id)
    if not owner:
        return False, {"error": "Project not found"}

    if owner.get("user_id") != requester_user_id:
        return False, {"error": "Only the project owner can remove members"}

    if member_user_id == owner.get("user_id"):
        return False, {"error": "Owner cannot be removed"}

    conn = get_db_connection()
    if not conn:
        return False, {"error": "Database connection error"}

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM project_collaborators
            WHERE module_name = %s
              AND project_id = %s
              AND user_id = %s
            """,
            (module_name, project_id, member_user_id),
        )
        if cur.rowcount == 0:
            return False, {"error": "Member not found"}

        conn.commit()
        return True, {"message": "Member removed"}

    except Exception as exc:
        conn.rollback()
        if _is_missing_table_error(exc):
            return False, {"error": "Project access tables are not initialized yet"}
        logger.error(
            "Error removing member module=%s project=%s user=%s: %s",
            module_name,
            project_id,
            member_user_id,
            exc,
        )
        return False, {"error": "Could not remove member"}
    finally:
        if cur:
            cur.close()
        conn.close()


def get_user_pending_invitations(user_id: int) -> List[Dict]:
    user = get_user_by_id(user_id)
    if not user:
        return []

    email = (user.get("email") or "").strip().lower()
    if not email:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                module_name,
                project_id,
                invitee_name,
                role,
                status,
                expires_at,
                created_at
            FROM project_invitations
            WHERE lower(invitee_email) = lower(%s)
              AND status = 'pending'
              AND expires_at >= NOW()
            ORDER BY created_at DESC
            """,
            (email,),
        )
        rows = cur.fetchall() or []

        output = []
        for row in rows:
            module_name = row.get("module_name")
            project_id = row.get("project_id")
            owner = get_project_owner(module_name, project_id)
            output.append(
                {
                    "id": row["id"],
                    "module_name": module_name,
                    "module_label": get_module_label(module_name),
                    "project_id": project_id,
                    "project_name": owner.get("name") if owner else f"Project {project_id}",
                    "role": row.get("role") or "viewer",
                    "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                }
            )

        return output
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        logger.error("Error listing pending invitations for user=%s: %s", user_id, exc)
        return []
    finally:
        if cur:
            cur.close()
        conn.close()
