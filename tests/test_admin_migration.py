"""Tests for Alembic migration 007_create_admin_auth_and_audit."""

import os
import subprocess
import sys


def test_alembic_history_single_head_007() -> None:
    """Verify Alembic history reports a single head at 007_create_admin_auth_and_audit."""
    cmd = [sys.executable, "-m", "alembic", "history"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = result.stdout.strip().splitlines()
    assert len(lines) >= 7
    assert "007_create_admin_auth_and_audit (head)" in lines[0]


def test_migration_007_upgrade_and_downgrade() -> None:
    """Verify upgrade to 007 and downgrade back to 006 executes cleanly."""
    db_file = "test_alembic_007.db"
    env = {"DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}

    try:
        # Upgrade to head (007)
        res_up = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env={**os.environ, **env},
            check=True,
        )
        assert res_up.returncode == 0

        # Downgrade to 006
        res_down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "006_create_crm_outbox_and_links"],
            capture_output=True,
            text=True,
            env={**os.environ, **env},
            check=True,
        )
        assert res_down.returncode == 0

        # Re-upgrade to head (007)
        res_reup = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env={**os.environ, **env},
            check=True,
        )
        assert res_reup.returncode == 0

    finally:
        if os.path.exists(db_file):
            os.remove(db_file)
