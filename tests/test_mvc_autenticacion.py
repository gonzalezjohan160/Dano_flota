"""Separación MVC de autenticación: login, logout y recuperación de contraseña."""
import ast
import datetime as dt
import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
os.environ["APP_ENV"] = "prod"
os.environ.setdefault("SECRET_KEY", "mvc-autenticacion-test")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-mvc-media-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

CLAVE = "Clave1234567x"
HASH_CLAVE = generate_password_hash(CLAVE)


class Cursor:
    def __init__(self, conexion):
        self.conexion = conexion
        self.filas = []
        self.rowcount = 1
        self.cerrado = 0

    def execute(self, sql, *parametros):
        texto = " ".join(sql.split())
        esc = self.conexion.escenario
        self.conexion.consultas.append((texto, parametros))
        if esc.get("falla") and esc["falla"] in texto:
            raise RuntimeError("fallo simulado de consulta")
        self.filas, self.rowcount = [], 1
        if "FROM usuario.Table_usuarios WHERE Username = ?" in texto:
            self.filas = esc.get("usuario", [])
        elif texto.startswith("SELECT ConsID FROM usuario.Table_usuarios WHERE Email = ?"):
            self.filas = esc.get("id_por_correo", [])
        elif texto.startswith("SELECT r.UserId"):
            self.filas = esc.get("enlace", [])
        elif "SET Used = 1 WHERE token = ?" in texto:
            self.rowcount = esc.get("filas_reclamadas", 1)
        elif texto.startswith("UPDATE usuario.Table_usuarios SET PasswordHash"):
            self.rowcount = esc.get("filas_contrasena", 1)
        return self

    def fetchone(self):
        return self.filas[0] if self.filas else None

    def close(self):
        self.cerrado += 1


class Conexion:
    def __init__(self, escenario):
        self.escenario = escenario
        self.consultas = []
        self.eventos = []
        self.cursor_simulado = Cursor(self)

    def cursor(self):
        return self.cursor_simulado

    def commit(self):
        self.eventos.append("commit")

    def rollback(self):
        self.eventos.append("rollback")

    def close(self):
        self.eventos.append("close")


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF no está instalado")
class MigracionAutenticacionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backend_interfaz
        import backend_login
        cls.interfaz = backend_interfaz
        cls.login = backend_login
        cls.app = backend_interfaz.Interfaz
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        self.interfaz.limiter.reset()
        self.correos = []
        self.conexiones = []
        self.escenario = {}
        self.parches = [
            patch.object(self.interfaz, "_validar_esquema_una_vez_por_proceso", return_value=None),
            patch.object(self.login, "connect", side_effect=self._conectar),
            patch.object(self.login, "cargar_permisos", return_value=["Ingresar_dashboard"]),
            patch.object(self.login, "enviar_email", side_effect=lambda d, l: self.correos.append((d, l))),
            patch.dict(os.environ, {"APP_BASE_URL": "https://gfd.example.co"}),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def _conectar(self):
        self.conexiones.append(Conexion(self.escenario))
        return self.conexiones[-1]

    def enlace_vigente(self, usado=0, minutos=20):
        return [(7, dt.datetime.now() + dt.timedelta(minutes=minutos), usado, "ana.p")]

    # Capas ----------------------------------------------------------------------
    def test_el_controlador_no_contiene_sql(self):
        codigo = (PROJECT_DIR / "backend" / "backend_login.py").read_text(encoding="utf-8")
        self.assertNotIn("execute(", codigo)
        self.assertIsNone(re.search(r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b", codigo))

    def test_el_modelo_no_importa_flask_ni_usa_la_sesion(self):
        arbol = ast.parse((PROJECT_DIR / "backend" / "modelos" / "autenticacion.py").read_text(encoding="utf-8"))
        importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
        importados |= {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(any(str(m).startswith("flask") for m in importados))
        self.assertFalse({n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} & {"request", "session"})

    # Login ----------------------------------------------------------------------
    def test_login_valido_abre_sesion(self):
        self.escenario["usuario"] = [(7, HASH_CLAVE, "10", 1, 0, "ana.p")]
        cliente = self.app.test_client()
        r = cliente.post("/", data={"username": "ana.p", "password": CLAVE})
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/interfaz"))
        with cliente.session_transaction() as sesion:
            self.assertEqual((sesion["usuario"], sesion["UF"], sesion["permisos"]), ("ana.p", "10", ["Ingresar_dashboard"]))
        self.assertEqual(self.conexiones[0].consultas[0][1], ("ana.p",))
        self.assertEqual(self.conexiones[0].eventos, ["close"])
        self.assertEqual(self.conexiones[0].cursor_simulado.cerrado, 1)

    def test_login_invalido_o_inactivo_no_abre_sesion(self):
        for usuario, clave in (([(7, HASH_CLAVE, "10", 1, 0, "ana.p")], "mala"), ([], CLAVE),
                               ([(7, HASH_CLAVE, "10", 0, 0, "ana.p")], CLAVE)):
            self.escenario["usuario"] = usuario
            cliente = self.app.test_client()
            r = cliente.post("/", data={"username": "ana.p", "password": clave})
            self.assertEqual(r.status_code, 200)
            with cliente.session_transaction() as sesion:
                self.assertNotIn("usuario", sesion)

    def test_login_con_cambio_obligatorio_va_al_perfil(self):
        self.escenario["usuario"] = [(7, HASH_CLAVE, "10", 1, 1, "ana.p")]
        r = self.app.test_client().post("/", data={"username": "ana.p", "password": CLAVE})
        self.assertEqual(r.headers["Location"], "/Profile/")

    def test_error_de_base_en_login_cierra_recursos_y_responde_generico(self):
        self.escenario["falla"] = "FROM usuario.Table_usuarios"
        r = self.app.test_client().post("/", data={"username": "ana.p", "password": CLAVE})
        self.assertEqual(r.status_code, 200)
        self.assertIn("No fue posible procesar el inicio de sesión", r.get_data(as_text=True))
        self.assertNotIn("fallo simulado", r.get_data(as_text=True))
        self.assertEqual(self.conexiones[0].eventos, ["close"])
        self.assertEqual(self.conexiones[0].cursor_simulado.cerrado, 1)

    def test_sexto_intento_fallido_responde_429(self):
        self.escenario["usuario"] = [(7, HASH_CLAVE, "10", 1, 0, "ana.p")]
        cliente = self.app.test_client()
        estados = [cliente.post("/", data={"username": "ana.p", "password": "mala"}).status_code for _ in range(6)]
        self.assertEqual(estados, [200] * 5 + [429])

    # Recuperación ---------------------------------------------------------------
    def test_recuperacion_guarda_solo_la_huella_y_envia_el_enlace(self):
        self.escenario["id_por_correo"] = [(7,)]
        r = self.app.test_client().post("/forgot-password", data={"email": "a@b.co"})
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/"))
        conexion = self.conexiones[0]
        orden = [sql.split()[0] for sql, _ in conexion.consultas]
        self.assertEqual(orden, ["SELECT", "UPDATE", "DELETE", "INSERT"])
        token = self.correos[0][1].rsplit("/", 1)[1]
        huella = conexion.consultas[3][1][0][1]
        self.assertNotEqual(huella, token)
        self.assertEqual(len(huella), 64)
        self.assertEqual(conexion.eventos, ["commit", "close"])

    def test_recuperacion_con_fallo_revierte_cierra_y_responde_igual(self):
        self.escenario.update(id_por_correo=[(7,)], falla="INSERT INTO usuario.Table_password_reset")
        r = self.app.test_client().post("/forgot-password", data={"email": "a@b.co"})
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/"))  # mensaje neutro de siempre
        self.assertEqual(self.conexiones[0].eventos, ["rollback", "close"])
        self.assertEqual(self.conexiones[0].cursor_simulado.cerrado, 1)
        self.assertEqual(self.correos, [])

    # Restablecimiento -----------------------------------------------------------
    def test_enlace_usado_vencido_o_inexistente_responde_400(self):
        for enlace, mensaje in ((self.enlace_vigente(usado=1), "Token ya utilizado"),
                                (self.enlace_vigente(minutos=-5), "Token expirado"),
                                ([], "Token inválido")):
            self.escenario["enlace"] = enlace
            r = self.app.test_client().post("/reset-password/abc", data={"password": "NuevaClave2026"})
            self.assertEqual((r.status_code, r.get_data(as_text=True)), (400, mensaje))

    def test_restablecimiento_exitoso_guarda_el_hash_y_confirma(self):
        self.escenario["enlace"] = self.enlace_vigente()
        r = self.app.test_client().post("/reset-password/abc", data={"password": "NuevaClave2026"})
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/"))
        conexion = self.conexiones[0]
        self.assertEqual(len(conexion.consultas[0][1][0]), 64)  # se busca por la huella, no por el token
        hash_guardado, id_usuario = conexion.consultas[2][1][0]
        self.assertTrue(check_password_hash(hash_guardado, "NuevaClave2026"))
        self.assertEqual(id_usuario, 7)
        self.assertEqual(conexion.eventos, ["commit", "close"])

    def test_enlace_reclamado_por_otro_pedido_revierte(self):
        self.escenario.update(enlace=self.enlace_vigente(), filas_reclamadas=0)
        r = self.app.test_client().post("/reset-password/abc", data={"password": "NuevaClave2026"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.conexiones[0].eventos, ["rollback", "close"])

    def test_fallo_al_cambiar_la_contrasena_revierte_cierra_y_no_expone_detalles(self):
        self.escenario.update(enlace=self.enlace_vigente(), falla="UPDATE usuario.Table_usuarios SET PasswordHash")
        with patch.object(self.login.logger, "exception") as registro:
            r = self.app.test_client().post("/reset-password/abc", data={"password": "NuevaClave2026"})
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_data(as_text=True), "No fue posible procesar la solicitud. Inténtelo nuevamente.")
        self.assertEqual(self.conexiones[0].eventos, ["rollback", "close"])
        self.assertEqual(self.conexiones[0].cursor_simulado.cerrado, 1)
        texto_log = " ".join(str(a) for a in registro.call_args.args)
        self.assertNotIn("abc", texto_log)  # ni el token
        self.assertNotIn("NuevaClave2026", texto_log)  # ni la contraseña

    def test_contrasena_debil_no_reclama_el_enlace(self):
        self.escenario["enlace"] = self.enlace_vigente()
        r = self.app.test_client().post("/reset-password/abc", data={"password": "a1"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(sql.startswith("UPDATE") for sql, _ in self.conexiones[0].consultas))

    def test_logout_limpia_la_sesion(self):
        cliente = self.app.test_client()
        with cliente.session_transaction() as sesion:
            sesion.update(usuario="ana.p", usuario_id=7, UF="10", permisos=[])
        r = cliente.post("/logout")
        self.assertEqual(r.headers["Location"], "/")
        with cliente.session_transaction() as sesion:
            self.assertNotIn("usuario", sesion)


if __name__ == "__main__":
    unittest.main()
