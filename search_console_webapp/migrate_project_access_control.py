#!/usr/bin/env python3
"""
Safe migration: add project-level access control tables.

This migration is idempotent and non-destructive:
- Creates new tables only if they do not exist
- Creates indexes only if they do not exist
- Does not update or delete existing project/user data
"""

import logging

from database import get_db_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_migration() -> bool:
    conn = get_db_connection()
    if not conn:
        logger.error("Could not connect to database")
        return False

    cur = None
    try:
        cur = conn.cursor()

        logger.info("Creating table project_collaborators (if missing)...")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS project_collaborators (
                id SERIAL PRIMARY KEY,
                module_name VARCHAR(32) NOT NULL CHECK (module_name IN ('llm_monitoring', 'manual_ai', 'ai_mode')),
                project_id INTEGER NOT NULL,
                owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer')),
                invited_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (module_name, project_id, user_id)
            )
            """
        )

        logger.info("Creating table project_invitations (if missing)...")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS project_invitations (
                id SERIAL PRIMARY KEY,
                module_name VARCHAR(32) NOT NULL CHECK (module_name IN ('llm_monitoring', 'manual_ai', 'ai_mode')),
                project_id INTEGER NOT NULL,
                owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                inviter_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                invitee_email TEXT NOT NULL,
                invitee_name TEXT,
                role VARCHAR(20) NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer')),
                token_hash TEXT NOT NULL UNIQUE,
                status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
                expires_at TIMESTAMP NOT NULL,
                accepted_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                accepted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )

        logger.info("Creating indexes...")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_collaborators_user ON project_collaborators(user_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_collaborators_project ON project_collaborators(module_name, project_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_collaborators_owner ON project_collaborators(owner_user_id)"
        )

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_invitations_project ON project_invitations(module_name, project_id, status)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_invitations_email ON project_invitations(lower(invitee_email))"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_invitations_owner ON project_invitations(owner_user_id, status)"
        )

        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_project_invitations_unique_pending
            ON project_invitations (module_name, project_id, lower(invitee_email))
            WHERE status = 'pending'
            """
        )

        conn.commit()
        logger.info("Migration project access control completed successfully")
        return True

    except Exception as exc:
        conn.rollback()
        logger.error("Migration failed: %s", exc)
        return False

    finally:
        if cur:
            cur.close()
        conn.close()


if __name__ == "__main__":
    ok = run_migration()
    raise SystemExit(0 if ok else 1)
