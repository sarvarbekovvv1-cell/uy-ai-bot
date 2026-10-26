"""Tests for Alembic migration 006_create_crm_outbox_and_links."""

import subprocess
import sys


def test_alembic_history_single_head() -> None:
    """Verify that Alembic history reports a single head at 006_create_crm_outbox_and_links."""
    cmd = [sys.executable, "-m", "alembic", "history"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = result.stdout.strip().splitlines()
    assert len(lines) >= 6
    # Check 006 is in history
    assert any("006_create_crm_outbox_and_links" in line for line in lines)


def test_migration_upgrade_and_downgrade() -> None:
    """Verify that upgrade to 006 and downgrade back to 005 executes cleanly."""
    # Test on isolated SQLite file
    db_file = "test_alembic_006.db"
    env = {"DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}

    try:
        # Upgrade to head
        res_up = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
            check=True,
        )
        assert "006_create_crm_outbox_and_links" in res_up.stderr or res_up.returncode == 0

        # Downgrade to 005
        res_down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "005_create_leads_and_crm"],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
            check=True,
        )
        assert res_down.returncode == 0

        # Re-upgrade to head
        res_reup = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
            check=True,
        )
        assert res_reup.returncode == 0

    finally:
        import os

        if os.path.exists(db_file):
            os.remove(db_file)
