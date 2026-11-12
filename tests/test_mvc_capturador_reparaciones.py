"""Separación MVC del Capturador de daños y del de reparaciones."""
import ast
import io
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PIL import Image

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
os.environ["APP_ENV"] = "prod"
os.environ.setdefault("SECRET_KEY", "mvc-capturador-test")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-mvc-media-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))
sys.path.insert(0, str(PROJECT_DIR / "tests"))

import backend_capturador  # noqa: E402
from catalogos_de_prueba import LISTAS, parchar_catalogos  # noqa: E402
import backend_reparaciones  # noqa: E402
from modelos import flota as modelo_flota  # noqa: E402

CONTROLADORES = ("backend_capturador.py", "backend_reparaciones.py")
MODELOS = ("modelos/flota.py", "modelos/capturador.py", "modelos/reparaciones.py")


class Cursor:
    """Cursor simulado: registra consultas y devuelve filas según la consulta."""

    def __init__(self, conexion):
        self.conexion = conexion
        self.cerrado = 0
        self.filas = []

    def execute(self, sql, *parametros):
        self.conexion.consultas.append((" ".join(sql.split()), parametros))
        if self.conexion.falla and (self.conexion.falla is True or self.conexion.falla in sql):
            raise RuntimeError("fallo simulado de consulta")
        texto = " ".join(sql.split())
        if texto.startswith("SELECT 1 FROM flota.table_Moviles"):
            self.filas = [(1,)]
        elif "OUTPUT INSERTED.ID" in texto:
            self.filas = [(321,)]
        elif texto.startswith("SELECT Tipologia_Movil FROM flota.table_Moviles"):
            self.filas = [("BUS",)]
        else:
            self.filas = []
        return self

    def fetchone(self):
        return self.filas[0] if self.filas else None

    def close(self):
        self.cerrado += 1


class Conexion:
    def __init__(self, falla=False):
        self.falla = falla
        self.consultas = []
        self.cerrado = 0
        self.commits = 0
        self.reversiones = 0
        self.cursor_simulado = Cursor(self)

    def cursor(self):
        return self.cursor_simulado

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.reversiones += 1

    def close(self):
        self.cerrado += 1


def imagen_png(nombre="foto.png"):
    salida = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(salida, format="PNG")
    salida.seek(0)
    return (salida, nombre)


class MigracionCapturadorReparacionesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__, template_folder=str(PROJECT_DIR / "frontend"))
        cls.app.secret_key = "solo-pruebas"
        cls.app.register_blueprint(backend_capturador.Capturador, url_prefix="/Capturador")
        cls.app.register_blueprint(backend_reparaciones.Capturador_rep, url_prefix="/Capturador_rep")
        cls.app.add_url_rule("/", endpoint="Modulo_login.login", view_func=lambda: "")

    def cliente(self, permisos=("Ingresar_captur_danos", "Ingresar_captur_reparaciones"), uf="10"):
        cliente = self.app.test_client()
        with cliente.session_transaction() as sesion:
            sesion.update(usuario="ana.p", usuario_id=7, permisos=list(permisos), UF=uf)
        return cliente

    def formulario_capturador(self, **cambios):
        datos = {
            "Fecha": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "UF": "10", "Movil": "Z32-1001", "Codigo": "1", "Nombre": "Ana", "Area": "OPERACIONES",
            "Ruta": "CG147", "Tipologia": "BUS", "Version_libre": "texto", "Parte_afectada": "ESPEJO",
            "Dano_ocasionado_por": LISTAS["tipos_dano"][0],
            "Zona_dano": LISTAS["zonas_dano"][0], "Centro_de_operaciones": "GAITANA",
            "Direccion": "Calle 1",
        }
        datos.update(cambios)
        return datos

    def formulario_reparacion(self, **cambios):
        datos = {"Movil": "Z32-1001", "UF": "10", "Tipologia": "BUS", "Zona_inter": "TECHO",
                 "Parte_intervenida": "LONA", "costo": "900"}
        datos.update(cambios)
        return datos

    def pedir(self, modulo, metodo, url, datos=None, falla=False):
        conexiones = []

        def conectar():
            conexiones.append(Conexion(falla=falla))
            return conexiones[-1]

        with patch.object(modulo, "connect", side_effect=conectar), parchar_catalogos():
            respuesta = self.cliente().open(
                url, method=metodo, data=datos,
                content_type="multipart/form-data" if metodo == "POST" else None)
        return respuesta, conexiones

    # 1. Los controladores no contienen SQL --------------------------------------
    def test_los_controladores_no_contienen_sql(self):
        for nombre in CONTROLADORES:
            codigo = (PROJECT_DIR / "backend" / nombre).read_text(encoding="utf-8")
            self.assertNotIn("execute(", codigo, nombre)
            self.assertIsNone(re.search(r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b", codigo), nombre)

    # 2. Los modelos no importan Flask ni usan request o session -----------------
    def test_los_modelos_no_importan_flask_ni_usan_la_sesion(self):
        for nombre in MODELOS:
            arbol = ast.parse((PROJECT_DIR / "backend" / nombre).read_text(encoding="utf-8"))
            importados = set()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    importados.update(alias.name.split(".")[0] for alias in nodo.names)
                elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                    importados.add(nodo.module.split(".")[0])
            self.assertNotIn("flask", importados, nombre)
            usados = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
            self.assertFalse(usados & {"request", "session"}, nombre)

    # 3. Conexión y cursor se cierran aunque falle una consulta ------------------
    def test_conexion_y_cursor_se_cierran_si_falla_una_consulta(self):
        casos = (
            (backend_capturador, "GET", "/Capturador/getConductor?codigo=7", None, 200),
            (backend_capturador, "GET", "/Capturador/getFlota?No_interno=1001", None, 200),
            (backend_capturador, "GET", "/Capturador/validarDuplicado?fecha=2026-10-01T10:00&movil=Z32-1&codigo=1&zona_dano=TECHO", None, 200),
            (backend_capturador, "GET", "/Capturador/validarDuplicado?fecha=mal", None, 200),
            (backend_capturador, "POST", "/Capturador/submit", self.formulario_capturador(), 500),
            (backend_reparaciones, "GET", "/Capturador_rep/getFlota?No_interno=1001", None, 200),
            (backend_reparaciones, "POST", "/Capturador_rep/submit", self.formulario_reparacion(), 500),
        )
        for modulo, metodo, url, datos, estado in casos:
            respuesta, conexiones = self.pedir(modulo, metodo, url, datos, falla=True)
            self.assertEqual(respuesta.status_code, estado, url)
            self.assertEqual(len(conexiones), 1, url)
            self.assertEqual(conexiones[0].cerrado, 1, f"{url}: la conexión debe cerrarse")
            self.assertEqual(conexiones[0].cursor_simulado.cerrado, 1, f"{url}: el cursor debe cerrarse")

    def test_al_fallar_el_guardado_se_revierte_antes_de_cerrar(self):
        for modulo, url, datos in (
                (backend_capturador, "/Capturador/submit", self.formulario_capturador()),
                (backend_reparaciones, "/Capturador_rep/submit", self.formulario_reparacion())):
            tabla = "flota.table_damage_to_fleet" if modulo is backend_capturador else "proceso.table_intervenciones"
            _, conexiones = self.pedir(modulo, "POST", url, datos, falla=f"INSERT INTO {tabla}")
            self.assertEqual(conexiones[0].reversiones, 1, url)
            self.assertEqual(conexiones[0].commits, 0, url)

    # 4. La consulta compartida de flota conserva parámetros y resultados -----------
    def test_flota_compartida_conserva_sql_parametros_y_resultado(self):
        conexion = Conexion()
        fila = modelo_flota.buscar_tipologia_del_movil(conexion.cursor(), "1001", (10, 16))
        sql, parametros = conexion.consultas[0]
        self.assertEqual(sql, "SELECT Tipologia_Movil FROM flota.table_Moviles WHERE No_Movil = ? AND UF IN (?, ?)")
        self.assertEqual(parametros, (("1001", 10, 16),))
        self.assertEqual(fila, ("BUS",))

        conexion = Conexion()
        self.assertTrue(modelo_flota.movil_pertenece_a_uf(conexion.cursor(), "Z32-1001", "10"))
        self.assertEqual(conexion.consultas[0],
                         ("SELECT 1 FROM flota.table_Moviles WHERE No_Movil = ? AND UF = ?", (("Z32-1001", 10),)))

    def test_los_dos_capturadores_usan_la_misma_consulta_de_flota(self):
        for url, respuesta_esperada in (
                ("/Capturador/getFlota?No_interno=1001", {"Tipologia_interno": "BUS", "movil_valido": True}),
                ("/Capturador_rep/getFlota?No_interno=1001", {"Tipologia_interno": "BUS"})):
            modulo = backend_capturador if url.startswith("/Capturador/") else backend_reparaciones
            with patch.object(modelo_flota, "buscar_tipologia_del_movil",
                              wraps=modelo_flota.buscar_tipologia_del_movil) as compartida:
                respuesta, _ = self.pedir(modulo, "GET", url)
            self.assertEqual(respuesta.get_json(), respuesta_esperada, url)
            self.assertEqual(compartida.call_args.args[1:], ("1001", (10,)), url)

    # 5. Permisos, validaciones y límites de carga se conservan --------------------
    def test_las_rutas_exigen_su_permiso(self):
        rutas = (("GET", "/Capturador/"), ("GET", "/Capturador/getFlota?No_interno=1"),
                 ("GET", "/Capturador/getConductor?codigo=1"), ("GET", "/Capturador/validarDuplicado"),
                 ("GET", "/Capturador/geocode?q=x"), ("POST", "/Capturador/submit"),
                 ("GET", "/Capturador_rep/"), ("GET", "/Capturador_rep/getFlota?No_interno=1"),
                 ("POST", "/Capturador_rep/submit"))
        for metodo, url in rutas:
            otro_modulo = ("Ingresar_captur_reparaciones",) if url.startswith("/Capturador/") else ("Ingresar_captur_danos",)
            respuesta = self.cliente(permisos=otro_modulo).open(url, method=metodo)
            self.assertEqual(respuesta.status_code, 403, url)

    def test_otra_uf_se_rechaza_sin_tocar_la_base(self):
        for modulo, url, datos in (
                (backend_capturador, "/Capturador/submit", self.formulario_capturador(UF="16")),
                (backend_reparaciones, "/Capturador_rep/submit", self.formulario_reparacion(UF="16"))):
            respuesta, conexiones = self.pedir(modulo, "POST", url, datos)
            self.assertEqual(respuesta.status_code, 403, url)
            self.assertEqual(conexiones, [], url)

    def test_limites_y_validacion_de_archivos_antes_de_tocar_la_base(self):
        # Cada envío necesita sus propios archivos: el test client los cierra al enviar.
        demasiados = lambda: {f"foto_{i}": imagen_png() for i in range(6)}  # noqa: E731
        falso = lambda: {"foto_0": (io.BytesIO(b"<svg onload=alert(1)>"), "foto.png")}  # noqa: E731
        grande = lambda: {"foto_0": (io.BytesIO(b"\x89PNG" + b"0" * (5 * 1024 * 1024 + 1)), "foto.png")}  # noqa: E731
        for adjuntos in (demasiados, falso, grande):
            for modulo, url, datos in (
                    (backend_capturador, "/Capturador/submit", self.formulario_capturador(**adjuntos())),
                    (backend_reparaciones, "/Capturador_rep/submit", self.formulario_reparacion(**adjuntos()))):
                respuesta, conexiones = self.pedir(modulo, "POST", url, datos)
                self.assertEqual(respuesta.status_code, 400, url)
                self.assertEqual(conexiones, [], url)

    def test_nombre_de_campo_con_ruta_no_sale_de_la_carpeta_de_la_reparacion(self):
        respuesta, conexiones = self.pedir(
            backend_reparaciones, "POST", "/Capturador_rep/submit",
            self.formulario_reparacion(**{"../../fuera": imagen_png()}))
        self.assertEqual(respuesta.status_code, 200, respuesta.get_data(as_text=True))
        carpeta = (backend_reparaciones.FILES_DIR / "321").resolve()
        rutas = [Path(p[0][2]) for sql, p in conexiones[0].consultas if "proceso.table_intervenciones_files" in sql]
        self.assertEqual(len(rutas), 1)
        self.assertEqual(rutas[0].resolve().parent, carpeta)
        self.assertEqual(conexiones[0].commits, 1)


if __name__ == "__main__":
    unittest.main()
