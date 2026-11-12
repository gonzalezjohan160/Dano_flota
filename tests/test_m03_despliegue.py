"""M-03: los archivos de despliegue están versionados y sin valores de un servidor."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
# Las pruebas escriben su log aparte, no en backend/logs/app.log.
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
ARCHIVOS_DESPLIEGUE = (
    "wsgi.py",
    "gunicorn.conf.py",
    "deploy/README.md",
    "deploy/supervisor/dano_flota.conf.template",
    "deploy/nginx/dano_flota.conf.template",
)


class DespliegueTests(unittest.TestCase):
    def test_archivos_de_despliegue_existen(self):
        for archivo in ARCHIVOS_DESPLIEGUE:
            self.assertTrue((PROJECT_DIR / archivo).is_file(), archivo)

    def test_sin_usuarios_ni_rutas_de_desarrollo(self):
        prohibidos = re.compile(r"em0\d{4}|/home/|/mnt/c|C:\\\\", re.IGNORECASE)
        for archivo in ARCHIVOS_DESPLIEGUE:
            texto = (PROJECT_DIR / archivo).read_text(encoding="utf-8")
            self.assertIsNone(prohibidos.search(texto), archivo)

    def test_env_example_declara_todas_las_variables_del_backend(self):
        usadas = set()
        for archivo in [*(PROJECT_DIR / "backend").glob("*.py"), PROJECT_DIR / "gunicorn.conf.py"]:
            usadas.update(re.findall(r"""os\.(?:getenv|environ\.get)\(\s*["']([A-Z_]+)""",
                                     archivo.read_text(encoding="utf-8")))
            usadas.update(re.findall(r"""os\.environ\[\s*["']([A-Z_]+)""",
                                     archivo.read_text(encoding="utf-8")))
        ejemplo = (PROJECT_DIR / ".env.example").read_text(encoding="utf-8")
        declaradas = set(re.findall(r"^([A-Z_]+)=", ejemplo, re.MULTILINE))
        opcionales = {"GUNICORN_LOGLEVEL"}
        self.assertEqual(sorted(usadas - declaradas - opcionales), [])

    def test_wsgi_expone_la_app(self):
        codigo = (
            "import wsgi; from flask import Flask; "
            "assert isinstance(wsgi.app, Flask); print(wsgi.app.name)"
        )
        entorno = dict(os.environ, SECRET_KEY="m03-test-only",
                       MEDIA_DIR=tempfile.mkdtemp(prefix="dano-flota-m03-"))
        r = subprocess.run([sys.executable, "-c", codigo], cwd=PROJECT_DIR, env=entorno,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("backend_interfaz", r.stdout)

    # M-02 (despliegue): Gunicorn no corre como root -----------------------------
    def cargar_conf_gunicorn(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location("gunicorn_conf", PROJECT_DIR / "gunicorn.conf.py")
        modulo = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {}, clear=False):
            spec.loader.exec_module(modulo)
        return modulo

    def test_gunicorn_se_niega_a_arrancar_como_root(self):
        from unittest.mock import patch
        conf = self.cargar_conf_gunicorn()
        with patch.object(conf.os, "geteuid", return_value=0, create=True):
            with self.assertRaises(SystemExit) as error:
                conf.on_starting(None)
        self.assertIn("root", str(error.exception))

    def test_gunicorn_arranca_con_usuario_de_servicio(self):
        from unittest.mock import patch
        conf = self.cargar_conf_gunicorn()
        with patch.object(conf.os, "geteuid", return_value=999, create=True), \
             patch.dict(os.environ, {"RATELIMIT_STORAGE_URI": "redis://localhost:6379"}):
            conf.on_starting(None)

    def test_gunicorn_exige_contador_compartido_con_varios_workers(self):
        from unittest.mock import patch
        conf = self.cargar_conf_gunicorn()
        with patch.object(conf.os, "geteuid", return_value=999, create=True), \
             patch.object(conf, "workers", 3):
            for uri in ("", "memory://"):
                with self.subTest(uri=uri), patch.dict(os.environ, {"RATELIMIT_STORAGE_URI": uri}):
                    with self.assertRaisesRegex(SystemExit, "RATELIMIT_STORAGE_URI"):
                        conf.on_starting(None)

    def test_supervisor_usa_usuario_parametrizado(self):
        texto = (PROJECT_DIR / "deploy/supervisor/dano_flota.conf.template").read_text(encoding="utf-8")
        usuarios = re.findall(r"^user=(.*)$", texto, re.MULTILINE)
        self.assertEqual(usuarios, ["${APP_USER}"])

    # B-05: el README documenta el despliegue completo, sin valores de desarrollo -
    def test_readme_cubre_el_despliegue_completo(self):
        texto = (PROJECT_DIR / "readme.md").read_text(encoding="utf-8")
        for paso in ("pip install -r requirements.txt", "manage_db.py migrate",
                     "manage_db.py preparar-carpetas", "gunicorn.conf.py", "wsgi:app",
                     "supervisorctl", "nginx -t", "APP_ENV", ".env.example"):
            self.assertIn(paso, texto, paso)
        for valor_dev in ("/mnt/c", "0.0.0.0", "--timeout 180", "~/.venvs", "em0000"):
            self.assertNotIn(valor_dev, texto, valor_dev)

    def test_readme_documenta_todas_las_variables_del_env(self):
        ejemplo = (PROJECT_DIR / ".env.example").read_text(encoding="utf-8")
        texto = (PROJECT_DIR / "readme.md").read_text(encoding="utf-8")
        for variable in re.findall(r"^([A-Z_]+)=", ejemplo, re.MULTILINE):
            self.assertIn(variable, texto, variable)

    # B-13: workers con hilos para que una espera de SQL Server no bloquee la app --
    def test_gunicorn_usa_workers_con_hilos(self):
        conf = self.cargar_conf_gunicorn()
        self.assertEqual(conf.worker_class, "gthread")
        self.assertGreater(conf.threads, 1)

    # B-04: archivos ajenos al proyecto fuera del repositorio ---------------------
    def test_archivos_ajenos_no_estan_en_git(self):
        r = subprocess.run(["git", "ls-files"], cwd=PROJECT_DIR, capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("no es un repositorio git")
        ajenos = [f for f in r.stdout.splitlines()
                  if re.search(r"start_venv\.ps1$|\.ssmssln$|\.ssmssqlproj$|\.deb$", f)]
        self.assertEqual(ajenos, [])


if __name__ == "__main__":
    unittest.main()
