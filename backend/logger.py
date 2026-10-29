import logging
import os
import re
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

try:
    import fcntl
except ImportError:  # Windows (solo desarrollo): sin bloqueo entre procesos
    fcntl = None

logger = logging.getLogger("dano_flota")

logger.setLevel(logging.INFO)

# APP_LOG_DIR permite escribir en otra carpeta; las pruebas la usan para no
# mezclar sus eventos con el app.log real.
LOG_DIR = os.getenv("APP_LOG_DIR") or os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "app.log")

# app.log rota al llegar a 10 MB y se conservan 5 archivos anteriores (app.log.1 … app.log.5).
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5


class ArchivoRotativoMultiproceso(RotatingFileHandler):
    """RotatingFileHandler apto para varios workers de Gunicorn escribiendo el mismo archivo.

    El estándar decide rotar según su propia posición de escritura, y cada
    proceso rota por su cuenta: se pisan los respaldos. Aquí el tamaño se mide
    sobre el archivo en disco, la rotación se hace con un bloqueo entre
    procesos y, si otro worker ya rotó, se reabre el app.log nuevo.
    """

    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._archivo_lock = self.baseFilename + ".lock"
        self._id_abierto = self._id_del_stream()

    def _id_del_stream(self):
        if self.stream is None:
            return None
        info = os.fstat(self.stream.fileno())
        return info.st_dev, info.st_ino

    def _reabrir_si_otro_proceso_roto(self):
        try:
            info = os.stat(self.baseFilename)
            en_disco = (info.st_dev, info.st_ino)
        except FileNotFoundError:
            en_disco = None
        if self.stream is None or en_disco != self._id_abierto:
            if self.stream:
                self.stream.close()
            self.stream = self._open()
            self._id_abierto = self._id_del_stream()

    @contextmanager
    def _bloqueo_entre_procesos(self):
        if fcntl is None:
            yield
            return
        with open(self._archivo_lock, "a") as bloqueo:
            fcntl.flock(bloqueo, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(bloqueo, fcntl.LOCK_UN)

    def _supera_el_limite(self, tamano_mensaje):
        try:
            tamano = os.path.getsize(self.baseFilename)
        except FileNotFoundError:
            return False
        return tamano > 0 and tamano + tamano_mensaje >= self.maxBytes

    def shouldRollover(self, record):
        self._reabrir_si_otro_proceso_roto()
        if self.maxBytes <= 0:
            return False
        self._tamano_mensaje = len((self.format(record) + self.terminator).encode("utf-8"))
        return self._supera_el_limite(self._tamano_mensaje)

    def doRollover(self):
        with self._bloqueo_entre_procesos():
            # Otro worker pudo rotar mientras se esperaba el bloqueo.
            self._reabrir_si_otro_proceso_roto()
            if not self._supera_el_limite(getattr(self, "_tamano_mensaje", 0)):
                return
            super().doRollover()
            self._id_abierto = self._id_del_stream()


file_handler = ArchivoRotativoMultiproceso(
    LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

file_handler.setFormatter(formatter)

logger.addHandler(file_handler)


_CARACTERES_DE_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def valor_para_log(valor, maximo=64):
    """Texto que escribió el usuario, sin saltos de línea ni caracteres de control
    (no puede inventar líneas falsas en el log) y recortado."""
    texto = _CARACTERES_DE_CONTROL.sub("?", str(valor if valor is not None else "-"))
    return texto[:maximo] or "-"


def contexto_peticion(usuario=None):
    """'usuario=… ip=…' para los eventos de autenticación.

    La IP es la del cliente: detrás de nginx la corrige ProxyFix con X-Forwarded-For.
    """
    from flask import has_request_context, request, session

    if not has_request_context():
        return f"usuario={valor_para_log(usuario)} ip=-"
    if usuario is None:
        usuario = session.get("usuario")
    return f"usuario={valor_para_log(usuario)} ip={valor_para_log(request.remote_addr, 45)}"
