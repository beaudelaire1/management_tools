import os
import subprocess
import sys


def test_portal_starts_with_only_the_parties_business_brick() -> None:
    environment = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "example_project.config.settings.portal_parties",
    }

    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "System check identified no issues" in result.stdout
