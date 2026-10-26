#!/usr/bin/env bash
set -euo pipefail
uv sync
uv run python manage.py migrate
uv run python manage.py import_school_data
uv run python manage.py runserver
