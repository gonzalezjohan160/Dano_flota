"""Separación MVC del módulo de Operaciones (subetapa 1 de backend_unificado.py)."""
import ast
import datetime as dt
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
os.environ["APP_ENV"] = "prod"
os.environ.setdefault("SECRET_KEY", "mvc-operaciones-test")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-mvc-media-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))
sys.path.insert(0, str(PROJECT_DIR / "tests"))
from catalogos_de_prueba import parchar_catalogos  # noqa: E402

import backend_unificado  # noqa: E402
from modelos import operaciones as modelo_operaciones  # noqa: E402

FUNCIONES_DE_OPERACIONES = (
    "actualizar_evento", "consultar_operador", "eliminar_evento",
    "obtener_reincidencia_operador", "verificar_reincidencia_operador", "agregar_operaciones",
)

CASO = {"Id": 7, "UF": "10", "Movil": "Z32-7001", "Codigo": "123", "Nombre": "ANA", "Area": "OBZ",
        "Ruta": "CG147", "Tipologia": "PADRÓN", "Direccion": "4.6,-74.1", "Version_libre": "x",
        "Parte_afectada": "ESPEJO", "Dano_ocasionado": "VANDALISMO", "Zona_dano": "FRONTAL",
        "Centro_operaciones": "GAITANA", "Fecha_evento": dt.datetime(2026, 10, 5, 5, 0),
        "Fecha_registro": dt.datetime(2026, 10, 6, 12, 51), "eliminado": 0, "estado_caso": 0}


class Cursor:
    """Cursor simulado que responde según la consulta y registra todo."""

    def __init__(self, conexion):
        self.conexion = conexion
        self.filas = []
        self.description = [("c",)]
        self.rowcount = 1
        self.cerrado = 0

    def execute(self, sql, *parametros):
        texto = " ".join(sql.split())
        esc = self.conexion.escenario
        self.conexion.consultas.append((texto, parametros))
        if esc.get("falla") and esc["falla"] in texto:
            raise RuntimeError("fallo simulado de consulta")
        self.filas, self.rowcount = [], 1
        if texto.startswith("SELECT CAST(m.UF AS varchar(3)), d.eliminado, d.estado_caso"):
            self.filas = [("10", 0, 0)]
        elif texto.startswith("SELECT d.Id_damage AS Id, d.fecha_evento AS Fecha_evento"):
            self.description = [(c,) for c in CASO]
            self.filas = [tuple(CASO.values())]
        elif texto.startswith("SELECT d.eliminado, CAST(m.UF AS varchar(3)), d.estado_caso"):
            self.filas = [(0, "10", 0)]
        elif "SET eliminado = 1" in texto:
            self.rowcount = esc.get("filas_eliminadas", 1)
        elif texto.startswith("SELECT Codigo, Fecha_evento"):
            self.filas = [("123", CASO["Fecha_evento"])]
        elif texto.startswith("SELECT COUNT(DISTINCT d.Id_damage)"):
            self.filas = [(esc.get("antecedentes", 0),)]
        elif "WITH (UPDLOCK, HOLDLOCK)" in texto:
            self.filas = [esc["gestion_anterior"]] if esc.get("gestion_anterior") else []
        elif texto.startswith("SELECT o.responsabilidad_operador"):
            self.filas = [("SI", "SI", 1, 1, 1, 0, 0)]
        elif texto.startswith("SELECT 1 FROM flota.table_Moviles"):
            self.filas = [(1,)]
        elif "FROM flota.table_drivers" in texto:
            self.filas = [("CONDUCTOR",)]
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


FORMULARIO = {"Id_damage_to_fleet": "7", "observaciones_1": "obs", "costo_supera_2m": "NO",
              "costo_valor": "1.500.000", "responsabilidad_operador": "SI", "conciliacion": "SI",
              "valor_conciliado_oper": "300.000", "Revinf": "SI"}


class MigracionOperacionesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.secret_key = "solo-pruebas"
        cls.app.register_blueprint(backend_unificado.Modulo_unificado, url_prefix="")

    def test_exige_responsabilidad_si_el_costo_no_supera_el_umbral(self):
        for valor in (None, "", "NULL"):
            with self.subTest(valor=valor):
                datos = dict(FORMULARIO)
                if valor is None:
                    datos.pop("responsabilidad_operador")
                else:
                    datos["responsabilidad_operador"] = valor
                respuesta, _ = self.pedir("POST", "/Operaciones/agregar_oper", data=datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("responsabilidad", respuesta.get_json()["message"])

    def pedir(self, metodo, url, escenario=None, *, permite_editar=True, **datos):
        conexiones = []

        def conectar():
            conexiones.append(Conexion(dict(escenario or {})))
            return conexiones[-1]

        cliente = self.app.test_client()
        with cliente.session_transaction() as sesion:
            permisos = ["Ingresar_modulo__oper", "Eliminar_evento", "Reabrir_caso_oper"]
            if permite_editar:
                permisos.append("Corregir_info_oper")
            sesion.update(usuario="ana.p", usuario_id=7, UF="10", permisos=permisos)
        with patch.object(backend_unificado, "connect", side_effect=conectar), parchar_catalogos():
            respuesta = cliente.open(url, method=metodo, **datos)
        # La última conexión es la de la operación (antes puede ir la del acceso por UF).
        return respuesta, conexiones

    def test_editar_evento_exige_permiso_de_correccion(self):
        respuesta, conexiones = self.pedir("POST", "/Operaciones/actualizar_evento/7", permite_editar=False)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(conexiones, [])

    # Capas ----------------------------------------------------------------------
    def test_funciones_de_operaciones_no_contienen_sql(self):
        # Desde la división del módulo unificado viven en unificado/operaciones*.py.
        funciones = {}
        for nombre in ("operaciones.py", "operaciones_evento.py"):
            codigo = (PROJECT_DIR / "backend" / "unificado" / nombre).read_text(encoding="utf-8")
            funciones.update({n.name: ast.get_source_segment(codigo, n) for n in ast.walk(ast.parse(codigo))
                              if isinstance(n, ast.FunctionDef) and n.name in FUNCIONES_DE_OPERACIONES})
        self.assertEqual(set(funciones), set(FUNCIONES_DE_OPERACIONES))
        for nombre, fuente in funciones.items():
            self.assertNotIn("execute(", fuente, nombre)
            self.assertIsNone(re.search(r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b", fuente), nombre)

    def test_modelos_no_importan_flask_ni_usan_la_sesion(self):
        for nombre in ("modelos/operaciones.py", "modelos/auditoria.py"):
            arbol = ast.parse((PROJECT_DIR / "backend" / nombre).read_text(encoding="utf-8"))
            importados = {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
            importados |= {n.module.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertNotIn("flask", importados, nombre)
            usados = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
            self.assertFalse(usados & {"request", "session"}, nombre)

    def test_solo_se_editan_columnas_de_la_lista_permitida(self):
        conexion = Conexion({})
        with self.assertRaises(ValueError):
            modelo_operaciones.actualizar_campo_del_caso(conexion.cursor(), 7, "eliminado = 1 --", "x")
        self.assertEqual(conexion.consultas, [])
        modelo_operaciones.actualizar_campo_del_caso(conexion.cursor(), 7, "Zona_dano", "TECHO")
        self.assertEqual(conexion.consultas,
                         [("UPDATE flota.table_damage_to_fleet SET Zona_dano = ? WHERE Id_damage = ?", (("TECHO", 7),))])

    # Cierre de recursos ---------------------------------------------------------
    def test_conexion_y_cursor_se_cierran_si_falla_una_consulta(self):
        casos = (
            ("POST", "/Operaciones/actualizar_evento/7", "UPDATE flota.table_damage_to_fleet SET",
             {"json": {"evento": {"Zona_dano": "TECHO"}, "motivo_modificacion": "m"}}, 500, True),
            ("GET", "/Operaciones/operador/555", "FROM flota.table_drivers", {}, 500, False),
            ("POST", "/Operaciones/eliminar_evento/7", "INSERT INTO proceso.table_auditoria_correcciones",
             {"json": {"motivo_modificacion": "m"}}, 500, True),
            ("GET", "/Operaciones/verificar_reincidencia/7", "COUNT(DISTINCT", {}, 500, False),
            ("POST", "/Operaciones/agregar_oper", "INSERT INTO proceso.table_info_oper", {"data": FORMULARIO}, 500, True),
        )
        for metodo, url, falla, datos, estado, revierte in casos:
            respuesta, conexiones = self.pedir(metodo, url, {"falla": falla}, **datos)
            self.assertEqual(respuesta.status_code, estado, url)
            conexion = conexiones[-1]
            self.assertEqual(conexion.eventos.count("close"), 1, f"{url}: la conexión debe cerrarse")
            self.assertEqual(conexion.cursor_simulado.cerrado, 1, f"{url}: el cursor debe cerrarse")
            if revierte:
                self.assertEqual(conexion.eventos, ["rollback", "close"], f"{url}: rollback antes de cerrar")

    # Consultas, parámetros, commits y rollbacks ---------------------------------
    def test_eliminar_registra_auditoria_y_borra_logicamente(self):
        respuesta, conexiones = self.pedir("POST", "/Operaciones/eliminar_evento/7",
                                           json={"motivo_modificacion": "duplicado"})
        self.assertEqual(respuesta.get_json()["message"], "Caso eliminado correctamente.")
        consultas = [sql.split(" (")[0] for sql, _ in conexiones[-1].consultas]
        self.assertEqual(consultas[1:], ["INSERT INTO proceso.table_auditoria_correcciones",
                                         "UPDATE flota.table_damage_to_fleet SET eliminado = 1 WHERE Id_damage = ? AND eliminado = 0"])
        self.assertEqual(conexiones[-1].consultas[1][1][0][-1], "duplicado")
        self.assertEqual(conexiones[-1].eventos, ["commit", "close"])

    def test_eliminar_ya_eliminado_revierte_y_responde_409(self):
        respuesta, conexiones = self.pedir("POST", "/Operaciones/eliminar_evento/7", {"filas_eliminadas": 0},
                                           json={"motivo_modificacion": "m"})
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(conexiones[-1].eventos, ["rollback", "close"])

    def test_reincidencia_cuenta_el_evento_actual(self):
        for antecedentes, eventos, bloqueado in ((0, 1, False), (2, 3, True)):
            respuesta, _ = self.pedir("GET", "/Operaciones/verificar_reincidencia/7", {"antecedentes": antecedentes})
            self.assertEqual(respuesta.get_json(), {"eventos": eventos, "bloqueado": bloqueado})

    def test_conciliacion_cierra_en_operaciones_con_el_mismo_orden(self):
        respuesta, conexiones = self.pedir("POST", "/Operaciones/agregar_oper", data=FORMULARIO)
        self.assertEqual(respuesta.get_json()["bloqueado_reincidencia"], False)
        orden = [" ".join(sql.split()[:3]) for sql, _ in conexiones[-1].consultas]
        self.assertEqual(orden, [
            "SELECT Codigo, Fecha_evento",   # reincidencia
            "SELECT COUNT(DISTINCT d.Id_damage)",
            "SELECT Observaciones_operaciones, usuario_id,",  # gestión anterior bloqueada
            "INSERT INTO proceso.table_info_oper",
            "SELECT Id_damage FROM",                    # ¿existe RRLL?
            "INSERT INTO proceso.table_info_labora",     # cierre por conciliación
            "SELECT o.responsabilidad_operador, o.conciliacion,",  # cierre automático
            "UPDATE flota.table_damage_to_fleet SET",
        ])
        insercion_rrll = conexiones[-1].consultas[5][1][0]
        self.assertEqual(insercion_rrll, ("7", "CONCILIACIÓN", 300000, 7))
        self.assertEqual(conexiones[-1].eventos, ["commit", "close"])

    def test_gestion_existente_sin_motivo_no_escribe_nada(self):
        anterior = ("viejo", "ana", "NO", None, 1000)
        respuesta, conexiones = self.pedir("POST", "/Operaciones/agregar_oper",
                                           {"gestion_anterior": anterior}, data=FORMULARIO)
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(any(sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql, _ in conexiones[-1].consultas))
        self.assertEqual(conexiones[-1].eventos, ["close"])


if __name__ == "__main__":
    unittest.main()
