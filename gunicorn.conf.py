
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Socket Unix detrás de nginx; Gunicorn no se expone en un puerto público.
bind = os.getenv("GUNICORN_BIND", "unix:/var/www/dano_flota/ipc.sock")
workers = int(os.getenv("GUNICORN_WORKERS", "3"))
# Varios hilos por worker: si una petición espera a SQL Server, las demás siguen
# atendiéndose (con workers síncronos, 3 esperas bloqueaban toda la app).
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# El socket queda sin acceso para "otros": solo el usuario de la app y el grupo de nginx.
umask = 0o007


def on_starting(server):
    """No arrancar como root: Supervisor debe usar el usuario de servicio (user=)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SystemExit(
            "Gunicorn no debe ejecutarse como root. Configure user= en Supervisor "
            "con el usuario de servicio (ver readme.md, sección 3)."
        )

    storage_uri = (os.getenv("RATELIMIT_STORAGE_URI") or "").strip()
    if workers > 1 and (not storage_uri or storage_uri.startswith("memory:")):
        raise SystemExit(
            "Configure RATELIMIT_STORAGE_URI con almacenamiento compartido "
            "(por ejemplo, redis://localhost:6379) para usar varios workers."
        )


# Logs a stdout/stderr: Supervisor los captura en sus archivos.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
