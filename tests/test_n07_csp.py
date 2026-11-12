import importlib
import importlib.util
import os
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
os.environ.setdefault("SECRET_KEY", "n07-test-only")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-n07-csp-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF is not installed")
class DashboardCspTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("backend_interfaz")
        cls.app = cls.module.Interfaz
        cls.app.config["TESTING"] = True

    @staticmethod
    def fake_connection():
        class Cursor:
            def execute(self, *args):
                pass

            def fetchone(self):
                # Activo, UF, Cambio_password_obligatorio
                return (1, "10", 0)

            def fetchall(self):
                # Permisos de las páginas que recorre la prueba (la autorización
                # central se aplica aunque la vista esté reemplazada).
                return [("Ingresar_dashboard",), ("Ingresar_historico_danos",),
                        ("Ingresar_danos_vs_reparaciones",), ("Ingresar_modulo__oper",)]

            def close(self):
                pass

        class Connection:
            def cursor(self):
                return Cursor()

            def close(self):
                pass

        return Connection()

    def test_dashboard_response_uses_nonce_csp_and_serializes_json_as_data(self):
        from flask import Response, render_template

        def dashboard_test_view(**kwargs):
            return render_template(
                "Front_dashboard.html",
                registros=[], costos=[], valores=[], operaciones=[], rrll=[], franjas=[],
                heatdata=[],
                ultimos_eventos=[{
                    "Movil": "10", "Fecha_evento": "08/10/2026", "Zona_dano": "Z",
                    "Parte_afectada": "<img src=x onerror=alert(1)>",
                }],
                vehiculos=[], lista_uf=[], uf_sel="", f_inicio="2026-10-01",
                f_fin="2026-10-08", ranking=[], ranking_rutas=[],
                ranking_registradores=[], zonas=[],
            )

        def strict_test_view(**kwargs):
            return Response("strict-policy-check")

        view_overrides = {
            "Front_dashboard.index": dashboard_test_view,
            "Historico_danos.index": strict_test_view,
            "Historico_movil.index": strict_test_view,
            "Modulo_unificado.index": strict_test_view,
        }

        with patch.dict(self.app.view_functions, view_overrides):
            with patch.object(self.module, "connect", side_effect=self.fake_connection), \
                    patch.object(self.module, "_validar_esquema_una_vez_por_proceso", return_value=None):
                client = self.app.test_client()
                with client.session_transaction() as session:
                    session["usuario"] = "test-user"
                    session["usuario_id"] = "test-user"
                    session["permisos"] = ["Ingresar_dashboard"]

                response = client.get("/Dashboard/")
                self.assertEqual(response.status_code, 200)
                policy = response.headers["Content-Security-Policy"]
                script_src = next(
                    directive.strip() for directive in policy.split(";")
                    if directive.strip().startswith("script-src ")
                )
                self.assertNotIn("'unsafe-inline'", script_src)
                self.assertIn("script-src-attr 'none'", policy)
                # Solo rutas exactas con versión fija; nunca el CDN completo.
                for origen in (
                    "https://unpkg.com/leaflet@1.9.4/dist/",
                    "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/",
                    "https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/",
                ):
                    self.assertIn(origen, script_src)
                for origen_amplio in ("https://unpkg.com ", "https://cdn.jsdelivr.net ", "https://leaflet.github.io"):
                    self.assertNotIn(origen_amplio, script_src + " ")

                nonce = script_src.split("'nonce-", 1)[1].split("'", 1)[0]
                html = response.get_data(as_text=True)
                self.assertIn(f'<script nonce="{nonce}">', html)
                self.assertNotIn("<img src=x onerror=alert(1)>", html)

                second_response = client.get("/Dashboard/")
                second_policy = second_response.headers["Content-Security-Policy"]
                second_script_src = next(
                    directive.strip() for directive in second_policy.split(";")
                    if directive.strip().startswith("script-src ")
                )
                second_nonce = second_script_src.split("'nonce-", 1)[1].split("'", 1)[0]
                self.assertNotEqual(nonce, second_nonce)

                for path in ("/Historico_danos/", "/Historico_movil/", "/Operaciones"):
                    prior_response = client.get(path)
                    self.assertEqual(prior_response.status_code, 200)
                    prior_script_src = next(
                        directive for directive in prior_response.headers["Content-Security-Policy"].split(";")
                        if directive.strip().startswith("script-src ")
                    )
                    self.assertNotIn("'unsafe-inline'", prior_script_src)
                    self.assertNotIn("https://leaflet.github.io", prior_script_src)


if __name__ == "__main__":
    unittest.main()
