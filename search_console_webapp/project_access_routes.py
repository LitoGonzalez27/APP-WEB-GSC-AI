"""Project access and invitation routes."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from auth import auth_required, get_current_user
from services.project_access_service import (
    accept_project_invitation,
    create_project_invitation,
    get_project_permissions,
    get_user_pending_invitations,
    list_project_invitations,
    list_project_members,
    remove_project_member,
    revoke_project_invitation,
    user_can_manage_project_access,
    user_can_view_project,
)

logger = logging.getLogger(__name__)

project_access_bp = Blueprint("project_access", __name__, url_prefix="/api/project-access")


@project_access_bp.route("/projects/<module_name>/<int:project_id>/permissions", methods=["GET"])
@auth_required
def get_permissions(module_name: str, project_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    permissions = get_project_permissions(user["id"], module_name, project_id)
    if not permissions.get("can_view"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    return jsonify({"success": True, "permissions": permissions})


@project_access_bp.route("/projects/<module_name>/<int:project_id>/members", methods=["GET"])
@auth_required
def get_project_members(module_name: str, project_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    if not user_can_view_project(user["id"], module_name, project_id):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    permissions = get_project_permissions(user["id"], module_name, project_id)
    members = list_project_members(module_name, project_id)
    invitations = list_project_invitations(module_name, project_id) if permissions.get("can_manage_access") else []

    return jsonify(
        {
            "success": True,
            "permissions": permissions,
            "members": members,
            "invitations": invitations,
        }
    )


@project_access_bp.route("/projects/<module_name>/<int:project_id>/invitations", methods=["POST"])
@auth_required
def create_invitation(module_name: str, project_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    if not user_can_manage_project_access(user["id"], module_name, project_id):
        return jsonify({"success": False, "error": "Only project owner can invite users"}), 403

    data = request.get_json(silent=True) or {}
    invitee_email = (data.get("email") or "").strip().lower()
    invitee_name = (data.get("name") or "").strip() or None
    role = (data.get("role") or "viewer").strip().lower()

    ok, payload = create_project_invitation(
        module_name=module_name,
        project_id=project_id,
        inviter_user_id=user["id"],
        invitee_email=invitee_email,
        invitee_name=invitee_name,
        role=role,
    )

    if not ok:
        return jsonify({"success": False, **payload}), 400

    return jsonify({"success": True, **payload}), 201


@project_access_bp.route("/projects/<module_name>/<int:project_id>/invitations", methods=["GET"])
@auth_required
def get_invitations(module_name: str, project_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    if not user_can_manage_project_access(user["id"], module_name, project_id):
        return jsonify({"success": False, "error": "Only project owner can view invitations"}), 403

    invitations = list_project_invitations(module_name, project_id)
    return jsonify({"success": True, "invitations": invitations})


@project_access_bp.route("/invitations/<int:invitation_id>", methods=["DELETE"])
@auth_required
def revoke_invitation(invitation_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    ok, payload = revoke_project_invitation(invitation_id, user["id"])
    if not ok:
        status_code = 403 if "owner" in (payload.get("error", "").lower()) else 400
        return jsonify({"success": False, **payload}), status_code

    return jsonify({"success": True, **payload})


@project_access_bp.route("/projects/<module_name>/<int:project_id>/members/<int:member_user_id>", methods=["DELETE"])
@auth_required
def remove_member(module_name: str, project_id: int, member_user_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    ok, payload = remove_project_member(
        module_name=module_name,
        project_id=project_id,
        member_user_id=member_user_id,
        requester_user_id=user["id"],
    )
    if not ok:
        status_code = 403 if "owner" in (payload.get("error", "").lower()) else 400
        return jsonify({"success": False, **payload}), status_code

    return jsonify({"success": True, **payload})


@project_access_bp.route("/invitations/accept", methods=["POST"])
@auth_required
def accept_invitation():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()

    ok, payload = accept_project_invitation(token=token, user_id=user["id"])
    if not ok:
        error = (payload.get("error") or "").lower()
        if "not found" in error:
            code = 404
        elif "does not match" in error or "unauthorized" in error:
            code = 403
        else:
            code = 400
        return jsonify({"success": False, **payload}), code

    return jsonify({"success": True, **payload})


@project_access_bp.route("/my-invitations", methods=["GET"])
@auth_required
def my_invitations():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    invitations = get_user_pending_invitations(user["id"])
    return jsonify({"success": True, "invitations": invitations})
