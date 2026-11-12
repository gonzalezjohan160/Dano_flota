"""Punto de entrada WSGI de producción.

Gunicorn se inicia desde la raíz del repositorio:
    gunicorn -c gunicorn.conf.py wsgi:app
"""
import sys
from pathlib import Path

# Los módulos del backend se importan entre sí por nombre (from config import ...).
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from backend_interfaz import Interfaz as app  # noqa: E402

__all__ = ["app"]
