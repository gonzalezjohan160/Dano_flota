import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
# Las pruebas escriben su log aparte, no en backend/logs/app.log.
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
TEST_MEDIA_DIR = tempfile.TemporaryDirectory(prefix="dano-flota-n07-")
os.environ["MEDIA_DIR"] = TEST_MEDIA_DIR.name
os.environ.setdefault("SECRET_KEY", "n07-test-only")
sys.path.insert(0, str(PROJECT_DIR / "backend"))
sys.path.insert(0, str(PROJECT_DIR / "tests"))

import backend_capturador as capturador  # noqa: E402
from catalogos_de_prueba import LISTAS, parchar_catalogos  # noqa: E402
from flask import Flask  # noqa: E402


class FakeCursor:
    def __init__(self):
        self.sql = ""
        self.insert_params = None

    def execute(self, sql, params=()):
        self.sql = sql
        if "INSERT INTO flota.caso" in sql:
            self.insert_params = params

    def fetchone(self):
        return (7001,) if "OUTPUT INSERTED.id" in self.sql else (1,)

    def close(self):
        # Como un cursor de pyodbc: el controlador lo cierra con closing().
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class CapturadorValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask("n07-capturador-test", template_folder=str(PROJECT_DIR / "frontend"))
        cls.app.secret_key = "n07-test-only"
        cls.app.jinja_env.globals["csrf_token"] = lambda: "test-token"
        cls.app.add_url_rule("/logout", endpoint="Modulo_login.logout", view_func=lambda: "")
        cls.app.add_url_rule("/videos", endpoint="Tutoriales.index", view_func=lambda: "")
        cls.app.register_blueprint(capturador.Capturador, url_prefix="/Capturador")
        cls.client = cls.app.test_client()
        cls.connections = []

    def setUp(self):
        with self.client.session_transaction() as session:
            session["usuario"] = "test-user"
            session["permisos"] = ["Ingresar_captur_danos"]
            session["UF"] = "10"
        self.connections.clear()
        self.connect_patch = patch.object(capturador, "connect", side_effect=self.fake_connect)
        self.connect_patch.start()
        self.addCleanup(self.connect_patch.stop)
        # Las listas salen de los catálogos de la base; aquí, de las de prueba.
        catalogos = parchar_catalogos()
        catalogos.start()
        self.addCleanup(catalogos.stop)

    def fake_connect(self):
        connection = FakeConnection()
        self.connections.append(connection)
        return connection

    def valid_form(self):
        return {
            "Fecha": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "UF": "10",
            "Movil": "10",
            "Codigo": "123",
            "Nombre": "Registro de prueba",
            "Area": "OPERACIONES",
            "Ruta": "CG147",
            "Tipologia": "TIPO DE PRUEBA",
            "Version_libre": "Modelo <válido> & texto libre",
            "Parte_afectada": "<img src=x onerror=alert(1)>",
            "Dano_ocasionado_por": LISTAS["tipos_dano"][0],
            "Zona_dano": LISTAS["zonas_dano"][0],
            "Inspector": "test-user",
            "Centro_de_operaciones": "GAITANA",
            "Direccion": "Bogotá",
        }

    def test_form_uses_same_allowlists_as_server_validation(self):
        response = self.client.get("/Capturador/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for value in LISTAS["zonas_dano"] + LISTAS["tipos_dano"] + LISTAS["centros_operacion"]:
            self.assertIn(f'<option value="{value}">{value}</option>', html)

    def no_se_escribio_nada(self):
        # La validación lee el catálogo, pero no inserta ni confirma nada.
        for conexion in self.connections:
            self.assertIsNone(conexion.cursor_instance.insert_params)
            self.assertFalse(conexion.committed)

    def test_invalid_zone_is_rejected_before_database_access(self):
        response = self.client.post(
            "/Capturador/submit", data={**self.valid_form(), "Zona_dano": "ZONA INVENTADA"}
        )
        self.assertEqual(response.status_code, 400)
        self.no_se_escribio_nada()

    def test_invalid_cause_is_rejected_before_database_access(self):
        response = self.client.post(
            "/Capturador/submit", data={**self.valid_form(), "Dano_ocasionado_por": "CAUSA INVENTADA"}
        )
        self.assertEqual(response.status_code, 400)
        self.no_se_escribio_nada()

    def test_ruta_de_otra_uf_se_rechaza_sin_escribir(self):
        response = self.client.post("/Capturador/submit", data={**self.valid_form(), "Ruta": "CL149"})
        self.assertEqual(response.status_code, 400)
        self.no_se_escribio_nada()

    def test_missing_required_field_is_rejected_before_database_access(self):
        form = self.valid_form()
        form.pop("Version_libre")
        response = self.client.post("/Capturador/submit", data=form)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.connections, [])

    def test_valid_lists_and_free_text_reach_parameterized_insert(self):
        response = self.client.post("/Capturador/submit", data=self.valid_form())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.connections[-1].cursor_instance.insert_params[7:9],
            ("Modelo <válido> & texto libre", "<img src=x onerror=alert(1)>"),
        )
        self.assertTrue(self.connections[-1].committed)

    def test_evento_futuro_se_rechaza_antes_de_tocar_la_base(self):
        # Fechas de evento posteriores al registro: confusión AM/PM o de día.
        from datetime import timedelta
        futura = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post("/Capturador/submit", data={**self.valid_form(), "Fecha": futura})
        self.assertEqual(response.status_code, 400)
        self.assertIn("AM o PM", response.get_json()["error"])
        self.assertEqual(self.connections, [])

    def test_user_cannot_submit_damage_for_another_uf(self):
        response = self.client.post(
            "/Capturador/submit", data={**self.valid_form(), "UF": "16"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.connections, [])

    def test_part_affected_respects_database_column_length(self):
        response = self.client.post(
            "/Capturador/submit", data={**self.valid_form(), "Parte_afectada": "x" * 201}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.connections, [])


if __name__ == "__main__":
    unittest.main()
