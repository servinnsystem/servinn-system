#!/usr/bin/env python
import os
import sys
import subprocess
from pathlib import Path


def main():
    """Run administrative tasks."""
    # A terminal opened before environment activation may use global Python.
    # Prefer this checkout's environment, while respecting any active venv.
    if sys.prefix == sys.base_prefix:
        local_python = Path(__file__).resolve().parent / 'env' / (
            'Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if local_python.is_file():
            try:
                result = subprocess.run([str(local_python), *sys.argv])
            except KeyboardInterrupt:
                raise SystemExit(130)
            raise SystemExit(result.returncode)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'servinn_core.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed "
            "and available on your PYTHONPATH environment variable? "
            "Did you forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
