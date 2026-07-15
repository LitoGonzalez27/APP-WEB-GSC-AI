"""
Tests del flujo mejorado de invitaciones (auto-accept OAuth + reenvío self-service)

- auto_accept_pending_invitations_for_email: acepta pendientes por email
  verificado, ignora proyectos borrados, y no toca nada si no hay pendientes.
- resend_invitation_to_self: solo el propio invitado (email coincidente) puede
  reenviarse una invitación pendiente; regenera token y extiende caducidad.

BD mockeada — no requiere conexión.
"""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services import project_access_service as pas


def _mock_conn(fetchall_rows=None, fetchone_row=None):
    cur = MagicMock()
    cur.fetchall.return_value = fetchall_rows or []
    cur.fetchone.return_value = fetchone_row
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def _invitation(inv_id=1, module="manual_ai", project_id=34, email="jon@example.com",
                status="pending", role="viewer"):
    return {
        "id": inv_id,
        "module_name": module,
        "project_id": project_id,
        "invitee_email": email,
        "invitee_name": "Jon",
        "role": role,
        "status": status,
        "inviter_user_id": 5,
        "expires_at": datetime.utcnow() + timedelta(days=3),
    }


class TestAutoAcceptPendingInvitations:

    def test_returns_empty_without_email_or_user(self):
        assert pas.auto_accept_pending_invitations_for_email(1, "") == []
        assert pas.auto_accept_pending_invitations_for_email(None, "a@b.com") == []

    def test_accepts_all_pending_for_email(self):
        rows = [
            _invitation(inv_id=1, module="manual_ai", project_id=34),
            _invitation(inv_id=2, module="llm_monitoring", project_id=32),
        ]
        conn, cur = _mock_conn(fetchall_rows=rows)

        with patch.object(pas, "get_db_connection", return_value=conn), \
             patch.object(pas, "get_project_owner",
                          return_value={"user_id": 5, "name": "Argal"}):
            accepted = pas.auto_accept_pending_invitations_for_email(665750, "JON@example.com")

        assert len(accepted) == 2
        assert accepted[0]["module_name"] == "manual_ai"
        assert accepted[0]["project_name"] == "Argal"
        assert accepted[0]["redirect_path"] == "/manual-ai/"
        assert accepted[1]["redirect_path"] == "/llm-monitoring"
        # 1 SELECT + (INSERT colaborador + UPDATE invitación) × 2
        assert cur.execute.call_count == 5
        conn.commit.assert_called_once()

    def test_skips_invitations_of_deleted_projects(self):
        conn, cur = _mock_conn(fetchall_rows=[_invitation()])

        with patch.object(pas, "get_db_connection", return_value=conn), \
             patch.object(pas, "get_project_owner", return_value=None):
            accepted = pas.auto_accept_pending_invitations_for_email(665750, "jon@example.com")

        assert accepted == []
        # Solo el SELECT inicial: ni upsert ni update
        assert cur.execute.call_count == 1

    def test_no_pending_no_writes(self):
        conn, cur = _mock_conn(fetchall_rows=[])
        with patch.object(pas, "get_db_connection", return_value=conn):
            accepted = pas.auto_accept_pending_invitations_for_email(665750, "jon@example.com")
        assert accepted == []
        assert cur.execute.call_count == 1


class TestResendInvitationToSelf:

    def test_rejects_when_email_does_not_match(self):
        conn, _ = _mock_conn(fetchone_row=_invitation(email="otra@persona.com"))
        with patch.object(pas, "get_db_connection", return_value=conn), \
             patch.object(pas, "get_user_by_id",
                          return_value={"id": 665750, "email": "jon@example.com"}):
            ok, payload = pas.resend_invitation_to_self(1, 665750)
        assert ok is False
        assert "another email" in payload["error"]

    def test_rejects_non_pending(self):
        conn, _ = _mock_conn(fetchone_row=_invitation(status="accepted"))
        with patch.object(pas, "get_db_connection", return_value=conn), \
             patch.object(pas, "get_user_by_id",
                          return_value={"id": 665750, "email": "jon@example.com"}):
            ok, payload = pas.resend_invitation_to_self(1, 665750)
        assert ok is False
        assert "accepted" in payload["error"]

    def test_resends_and_regenerates_token(self):
        conn, cur = _mock_conn(fetchone_row=_invitation())
        sent = {}

        def fake_send(**kwargs):
            sent.update(kwargs)
            return True

        with patch.object(pas, "get_db_connection", return_value=conn), \
             patch.object(pas, "get_user_by_id",
                          return_value={"id": 665750, "email": "jon@example.com"}), \
             patch.object(pas, "get_project_owner",
                          return_value={"user_id": 5, "name": "Argal"}), \
             patch.object(pas, "_send_project_invitation_email", side_effect=fake_send):
            ok, payload = pas.resend_invitation_to_self(1, 665750)

        assert ok is True
        assert payload["email_sent"] is True
        # El email va SOLO al propio invitado
        assert sent["to_email"] == "jon@example.com"
        assert "project-invitations/accept?token=" in sent["invitation_link"]
        # UPDATE de token_hash + expires_at ejecutado
        update_sql = cur.execute.call_args_list[1][0][0]
        assert "token_hash" in update_sql and "expires_at" in update_sql
        conn.commit.assert_called_once()
