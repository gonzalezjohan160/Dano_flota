"""MVC-5: configuración por entorno con APP_ENV y sin efectos al importar config."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
# Las pruebas escriben su log aparte, no en backend/logs/app.log.
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
os.environ.setdefault("SECRET_KEY", "mvc5-test-only")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-mvc5-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))


class ConfiguracionPorEntornoTests(unittest.TestCase):
    def activa(self, valor):
        import config
        entorno = {} if valor is None else {"APP_ENV": valor}
        with patch.dict(os.environ, entorno):
            if valor is None:
                os.environ.pop("APP_ENV", None)
            return config.configuracion_activa()

    def test_sin_app_env_se_usa_produccion(self):
        self.assertEqual(self.activa(None).NOMBRE_ENTORNO, "prod")

    def test_app_env_selecciona_la_configuracion(self):
        for valor, nombre in (("dev", "dev"), ("QA", "qa"), (" prod ", "prod")):
            self.assertEqual(self.activa(valor).NOMBRE_ENTORNO, nombre)

    def test_app_env_invalido_detiene_el_arranque(self):
        with self.assertRaises(RuntimeError):
            self.activa("produccion")

    def test_qa_y_produccion_son_estrictos(self):
        for valor in ("qa", "prod"):
            cfg = self.activa(valor)
            self.assertFalse(cfg.DEBUG, valor)
            self.assertTrue(cfg.SESSION_COOKIE_SECURE, valor)
            self.assertTrue(cfg.SESSION_COOKIE_HTTPONLY, valor)

    def test_desarrollo_permite_http_local(self):
        cfg = self.activa("dev")
        self.assertTrue(cfg.DEBUG)
        self.assertFalse(cfg.SESSION_COOKIE_SECURE)

    def test_app_usa_la_configuracion_del_entorno(self):
        codigo = ("import backend_interfaz as b; c = b.Interfaz.config; "
                  "print(c['SESSION_COOKIE_SECURE'], c['DEBUG'], c['MAX_CONTENT_LENGTH'])")
        for entorno, esperado in (("dev", "False True"), ("prod", "True False")):
            env = dict(os.environ, APP_ENV=entorno)
            r = subprocess.run([sys.executable, "-c", codigo], cwd=PROJECT_DIR / "backend",
                               env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.strip().startswith(esperado), r.stdout)

    def test_importar_config_no_crea_carpetas(self):
        # Importar config no toca la carpeta de TI; preparar-carpetas crea las de cada
        # módulo (aquí, redirigidas a una carpeta temporal).
        media = Path(tempfile.mkdtemp(prefix="dano-flota-mvc5-vacia-")) / "media"
        codigo = (
            "import os\nfrom pathlib import Path\n"
            "antes = Path('/media/emapp/dano_flota/Files').exists()\n"
            "import config\n"
            "assert Path('/media/emapp/dano_flota/Files').exists() == antes\n"
            "media = Path(os.environ['MEDIA_PRUEBA'])\n"
            "for k, v in list(config.UPLOAD_FOLDERS.items()):\n"
            "    config.UPLOAD_FOLDERS[k] = media / 'Files' / v.name\n"
            "config.crear_carpetas_media()\n"
        )
        r = subprocess.run([sys.executable, "-c", codigo], cwd=PROJECT_DIR / "backend",
                           env=dict(os.environ, MEDIA_PRUEBA=str(media)), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((media / "Files" / "Files_ppal").is_dir())

if __name__ == "__main__":
    unittest.main()
