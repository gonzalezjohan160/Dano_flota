"""B-04: app.log rota por tamaño (también con varios workers) y los eventos de
autenticación registran usuario e IP."""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
sys.path.insert(0, str(PROJECT_DIR / "backend"))


class RotacionTests(unittest.TestCase):
    def test_rota_al_superar_el_tamano_y_conserva_los_respaldos(self):
        import logging
        from logger import ArchivoRotativoMultiproceso
        carpeta = Path(tempfile.mkdtemp(prefix="dano-flota-rotacion-"))
        handler = ArchivoRotativoMultiproceso(str(carpeta / "app.log"), maxBytes=500, backupCount=3)
        log = logging.getLogger("prueba_rotacion")
        log.propagate = False
        log.addHandler(handler)
        try:
            for i in range(200):
                log.warning("evento de prueba %04d", i)
        finally:
            log.removeHandler(handler)
            handler.close()
        archivos = sorted(p.name for p in carpeta.iterdir()
                          if p.name.startswith("app.log") and not p.name.endswith(".lock"))
        self.assertEqual(archivos, ["app.log", "app.log.1", "app.log.2", "app.log.3"])
        for nombre in archivos:
            self.assertLessEqual((carpeta / nombre).stat().st_size, 500, nombre)

    @unittest.skipIf(sys.platform == "win32", "el bloqueo entre procesos usa fcntl")
    def test_varios_procesos_rotan_sin_perder_lineas(self):
        carpeta = Path(tempfile.mkdtemp(prefix="dano-flota-multiproceso-"))
        procesos, lineas = 4, 300
        codigo = textwrap.dedent(f"""
            import logging, sys
            sys.path.insert(0, {str(PROJECT_DIR / "backend")!r})
            from logger import ArchivoRotativoMultiproceso
            h = ArchivoRotativoMultiproceso({str(carpeta / "app.log")!r}, maxBytes=4000, backupCount=500)
            h.setFormatter(logging.Formatter("%(message)s"))
            log = logging.getLogger("p"); log.propagate = False; log.addHandler(h)
            for i in range({lineas}):
                log.warning("proceso %s linea %04d", sys.argv[1], i)
        """)
        hijos = [subprocess.Popen([sys.executable, "-c", codigo, str(n)]) for n in range(procesos)]
        for hijo in hijos:
            self.assertEqual(hijo.wait(timeout=120), 0)
        escritas = []
        for archivo in carpeta.glob("app.log*"):
            if not archivo.name.endswith(".lock"):
                escritas += archivo.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(escritas), procesos * lineas, "se perdieron o duplicaron líneas")
        self.assertEqual(len(set(escritas)), procesos * lineas)
        self.assertGreater(len(list(carpeta.glob("app.log.*"))), 1, "no hubo rotación")


class ContextoDeAutenticacionTests(unittest.TestCase):
    def test_valor_para_log_no_permite_inventar_lineas(self):
        from logger import valor_para_log
        self.assertEqual(valor_para_log("ana\n2026 | INFO | login_exitoso"), "ana?2026 | INFO | login_exitoso")
        self.assertEqual(len(valor_para_log("x" * 500)), 64)
        self.assertEqual(valor_para_log(None), "-")

    def test_las_pruebas_no_escriben_en_el_app_log_real(self):
        import logger
        self.assertNotEqual(Path(logger.LOG_FILE).resolve(),
                            (PROJECT_DIR / "backend" / "logs" / "app.log").resolve())


if __name__ == "__main__":
    unittest.main()
