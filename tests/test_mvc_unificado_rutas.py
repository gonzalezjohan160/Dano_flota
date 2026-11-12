"""División del módulo unificado: rutas, respuestas, SQL, transacciones y permisos.

Base SIMULADA: ninguna prueba se conecta a SQL Server. La fachada backend_unificado
conserva connect y verificar_acceso_uf_caso, así que basta sustituirlos ahí.
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-unificado-media-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from flask import Flask  # noqa: E402

import backend_unificado  # noqa: E402
from modelos import archivos as modelo_archivos  # noqa: E402

TODOS = ["Ingresar_modulo__oper", "Ingresar_modulo__mtto", "Ingresar_modulo__svial",
         "Ingresar_modulo__laboral", "Reabrir_caso_oper", "Reabrir_caso_rr_ll"]

ENDPOINTS = {
    "index": ("/<modulo>", {"GET"}),
    "detalle": ("/<modulo>/detalle/<int:id>", {"GET"}),
    "opciones_evento": ("/<modulo>/opciones_evento", {"GET"}),
    "actualizar_evento": ("/<modulo>/actualizar_evento/<int:id>", {"POST"}),
    "consultar_operador": ("/Operaciones/operador/<codigo>", {"GET"}),
    "eliminar_evento": ("/Operaciones/eliminar_evento/<int:id>", {"POST"}),
    "reabrir_evento": ("/Operaciones/reabrir_evento/<int:id>", {"POST"}),
    "reabrir_evento_laboral": ("/laboral/reabrir_evento/<int:id>", {"POST"}),
    "descargar_archivo": ("/archivo/<int:file_id>", {"GET"}),
    "verificar_reincidencia_operador": ("/Operaciones/verificar_reincidencia/<int:id>", {"GET"}),
    "agregar": ("/<modulo>/<accion>", {"POST"}),
}


class Cursor:
    def __init__(self, conexion):
        self.conexion = conexion
        self.description = [("c",)]
        self.filas = []
        self.rowcount = 1

    def execute(self, sql, *params):
        texto = " ".join(sql.split())
        valores = list(params[0]) if len(params) == 1 and isinstance(params[0], (list, tuple)) else list(params)
        self.conexion.consultas.append((texto, valores))
        if self.conexion.falla and self.conexion.falla in texto:
            raise RuntimeError("detalle interno que no debe llegar al cliente")
        self.filas = next((list(filas) for inicio, filas in self.conexion.respuestas.items()
                           if texto.startswith(inicio)), [])
        return self

    def fetchone(self):
        return self.filas[0] if self.filas else None

    def fetchall(self):
        return list(self.filas)

    def nextset(self):
        return False

    def close(self):
        self.conexion.eventos.append("cursor.close")


class Conexion:
    def __init__(self, respuestas, falla=None):
        self.respuestas, self.falla = respuestas, falla
        self.consultas, self.eventos = [], []

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.eventos.append("commit")

    def rollback(self):
        self.eventos.append("rollback")

    def close(self):
        self.eventos.append("close")


def caso(uf="10", eliminado=0, cerrado=0):
    return {"SELECT CAST(m.UF AS varchar(3)), d.eliminado, d.estado_caso": [(uf, eliminado, cerrado)]}


class RutasDelModuloUnificadoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask("prueba_unificado")
        cls.app.secret_key = "prueba"
        cls.app.register_blueprint(backend_unificado.Modulo_unificado, url_prefix="")

    def pedir(self, metodo, url, respuestas=None, falla=None, permisos=TODOS, uf="10", **datos):
        conexiones = []

        def nueva_conexion():
            conexiones.append(Conexion(respuestas or {}, falla))
            return conexiones[-1]

        cliente = self.app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["usuario"], sesion["UF"], sesion["permisos"] = "ana.p", uf, list(permisos)
            sesion["usuario_id"] = 7
        with patch.object(backend_unificado, "connect", side_effect=nueva_conexion), \
                patch("unificado.archivos.logger"), patch("unificado.gestiones.logger"), \
                patch("unificado.laboral.logger"), patch("unificado.reapertura.logger"):
            respuesta = cliente.open(url, method=metodo, **datos)
        return respuesta, conexiones

    def escrituras(self, conexion):
        return [(sql, args) for sql, args in conexion.consultas if sql.startswith(("INSERT", "UPDATE", "DELETE"))]

    # Rutas y registro ----------------------------------------------------------------
    def test_endpoints_urls_y_metodos_se_conservan(self):
        reglas = {r.endpoint.split(".", 1)[1]: (r.rule, r.methods - {"HEAD", "OPTIONS"})
                  for r in self.app.url_map.iter_rules() if r.endpoint.startswith("Modulo_unificado.")}
        reglas.pop("static")
        self.assertEqual(reglas, ENDPOINTS)

    def test_cada_ruta_se_registra_una_vez_y_tiene_regla_central(self):
        import importlib
        from autorizacion import REGLAS
        for nombre in ("bandeja", "detalle", "archivos", "gestiones", "laboral", "operaciones",
                       "operaciones_evento", "reapertura"):
            importlib.import_module(f"unificado.{nombre}")
        self.assertEqual(len(backend_unificado.Modulo_unificado.deferred_functions), len(ENDPOINTS))
        for endpoint in ENDPOINTS:
            self.assertIn(f"Modulo_unificado.{endpoint}", REGLAS)

    # Mantenimiento ------------------------------------------------------------------
    def test_mtto_nuevo_inserta_marca_y_responde_estado_de_ot(self):
        respuestas = dict(caso(), **{"SELECT m.estado_mtto, o.Id_damage": [(1, 7, "NO", None)]})
        respuesta, conexiones = self.pedir("POST", "/Mtto/agregar_mtto", respuestas, data={
            "Id_damage_to_fleet": "7", "Costo": "$ 1.200", "dano_adicional": "NO", "observaciones": "obs",
            "Usuario_registro_mtto": "otro"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(set(respuesta.get_json()), {"status", "message", "estado_mtto", "pendiente_ot"})
        self.assertEqual(respuesta.get_json()["pendiente_ot"], False)
        gestion = conexiones[-1]
        self.assertEqual(self.escrituras(gestion)[0][1], ["7", 1200, "NO", "obs", 7])
        self.assertTrue(self.escrituras(gestion)[1][0].startswith("UPDATE proceso.table_info_mtto SET estado_mtto = 1"))
        self.assertEqual(gestion.eventos, ["commit", "cursor.close", "close"])

    def test_mtto_existente_audita_el_cambio_y_actualiza(self):
        respuestas = dict(caso(), **{"SELECT 1 FROM proceso.v_BD6_table_info_mtto": [(1,)],
                                     "SELECT Costo, dano_adicional, observaciones": [(500, "NO", "obs")],
                                     "SELECT m.estado_mtto, o.Id_damage": [(1, None, None, None)]})
        _, conexiones = self.pedir("POST", "/Mtto/agregar_mtto", respuestas, data={
            "Id_damage_to_fleet": "7", "Costo": "900", "dano_adicional": "NO", "observaciones": "obs",
            "Motivo_modificacion": "ajuste"})
        escritas = self.escrituras(conexiones[-1])
        self.assertTrue(escritas[0][0].startswith("INSERT INTO proceso.table_auditoria_correcciones"))
        self.assertEqual(escritas[0][1][:5], ["7", "proceso.table_info_mtto", "costo", "500", "900"])
        self.assertEqual(escritas[1][1], [900, "NO", "obs", 7, "7"])

    def test_mtto_costo_invalido_responde_400_sin_abrir_la_gestion(self):
        respuesta, conexiones = self.pedir("POST", "/Mtto/agregar_mtto", caso(), data={
            "Id_damage_to_fleet": "7", "Costo": "1,5x"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(len(conexiones), 1)  # solo la verificación de UF del caso

    def test_falla_en_gestion_revierte_cierra_y_no_revela_el_error(self):
        for url, datos, falla in (
            ("/Mtto/agregar_mtto", {"Costo": "1"}, "INSERT INTO proceso.table_info_mtto"),
            ("/Svial/agregar_svial", {"Observaciones_svial": "s"}, "INSERT INTO proceso.table_info_svial"),
            ("/laboral/agregar_rl", {"observaciones_1": "o", "Estado_caso": "COMPLETO"}, "INSERT INTO proceso.table_info_laboral_mult"),
        ):
            with self.subTest(url=url):
                respuesta, conexiones = self.pedir("POST", url, caso(), falla=falla,
                                                   data=dict(datos, Id_damage_to_fleet="7"))
                self.assertEqual(respuesta.status_code, 500)
                self.assertNotIn("detalle interno", respuesta.get_data(as_text=True))
                self.assertEqual(conexiones[-1].eventos,
                                 ["rollback", "cursor.close", "close"])
                self.assertEqual(conexiones[0].eventos, ["cursor.close", "close"])

    # Seguridad Vial -----------------------------------------------------------------
    def test_svial_convierte_el_valor_y_cierra_el_caso_si_corresponde(self):
        respuestas = dict(caso(), **{"SELECT o.responsabilidad_operador": [("NO APLICA", None, 1, 1, 1, 0, 0)]})
        respuesta, conexiones = self.pedir("POST", "/Svial/agregar_svial", respuestas, data={
            "Id_damage_to_fleet": "7", "Observaciones_svial": "s", "conciliado_a_favor": "empresa",
            "valor_conciliado_terceros": "$ 50.000"})
        self.assertEqual(respuesta.get_json(), {"status": "success", "message": "Registro guardado correctamente."})
        escritas = self.escrituras(conexiones[-1])
        self.assertEqual(escritas[0][1], ["7", "s", 7, "empresa", 50000])
        self.assertEqual(escritas[-1], ("UPDATE flota.table_damage_to_fleet SET estado_caso = 1 WHERE Id_damage = ?", ["7"]))

    # Relaciones Laborales -----------------------------------------------------------
    def test_rrll_devuelve_procesos_a_pendiente_y_cierra(self):
        respuesta, conexiones = self.pedir("POST", "/laboral/agregar_rl", caso(), data={
            "Id_damage_to_fleet": "7", "observaciones_1": "o", "Estado_caso": "operaciones, MANTENIMIENTO",
            "Revinf": "SI", "Tipo_cerrado_input": "CONCILIACIÓN", "Costo": "200.000"})
        self.assertEqual(respuesta.status_code, 200)
        escritas = self.escrituras(conexiones[-1])
        self.assertEqual(escritas[0][1][2], "MANTENIMIENTO, OPERACIONES")
        self.assertEqual([sql for sql, _ in escritas[1:3]], [
            "UPDATE proceso.table_info_mtto SET estado_mtto = 0 WHERE Id_damage = ?",
            "UPDATE proceso.table_info_oper SET estado_oper = 0 WHERE Id_damage = ?"])
        self.assertEqual(escritas[3][1], ["7", "CONCILIACIÓN", 200000, 7])
        self.assertEqual(escritas[4], ("UPDATE flota.table_damage_to_fleet SET estado_caso = 1 WHERE Id_damage = ?", ["7"]))
        self.assertEqual(conexiones[-1].eventos, ["commit", "cursor.close", "close"])

    def test_rrll_completo_con_otro_proceso_responde_400(self):
        respuesta, conexiones = self.pedir("POST", "/laboral/agregar_rl", caso(), data={
            "Id_damage_to_fleet": "7", "observaciones_1": "o", "Estado_caso": "COMPLETO, OPERACIONES"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(len(conexiones), 1)

    # Reapertura ---------------------------------------------------------------------
    def test_reabrir_registra_auditoria_y_abre_el_caso(self):
        respuestas = {"SELECT CAST(m.UF AS varchar(3)), d.estado_caso, 1": [("10", 1, 1)]}
        respuesta, conexiones = self.pedir("POST", "/Operaciones/reabrir_evento/7", respuestas,
                                           json={"motivo_modificacion": "revisión"})
        self.assertEqual(respuesta.get_json()["status"], "success")
        escritas = self.escrituras(conexiones[-1])
        self.assertEqual(escritas[0], ("UPDATE flota.table_damage_to_fleet SET estado_caso = 0 WHERE Id_damage = ?", [7]))
        self.assertEqual(escritas[1][1][:5], [7, "flota.table_damage_to_fleet", "estado_caso", "1", "0"])

    def test_reabrir_desde_rrll_exige_cierre_de_rrll_y_permiso(self):
        respuestas = {"SELECT CAST(m.UF AS varchar(3)), d.estado_caso, CASE": [("10", 1, 0)]}
        respuesta, conexiones = self.pedir("POST", "/laboral/reabrir_evento/7", respuestas,
                                           json={"motivo_modificacion": "m"})
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(self.escrituras(conexiones[-1]), [])
        sin_permiso, _ = self.pedir("POST", "/laboral/reabrir_evento/7", respuestas, permisos=TODOS[:4],
                                    json={"motivo_modificacion": "m"})
        self.assertEqual(sin_permiso.status_code, 403)

    # UF y eliminación lógica -----------------------------------------------------------
    def test_caso_de_otra_uf_o_eliminado_no_se_consulta_ni_gestiona(self):
        for respuestas, esperado in ((caso(uf="16"), 403), (caso(eliminado=1), 404)):
            for metodo, url, datos in (("GET", "/Mtto/detalle/7", {}),
                                       ("POST", "/Svial/agregar_svial", {"data": {"Id_damage_to_fleet": "7"}})):
                with self.subTest(url=url, esperado=esperado):
                    respuesta, conexiones = self.pedir(metodo, url, respuestas, **datos)
                    self.assertEqual(respuesta.status_code, esperado)
                    self.assertEqual(len(conexiones), 1)
                    self.assertEqual(conexiones[0].eventos, ["cursor.close", "close"])

    def test_bandeja_filtra_por_uf_de_la_sesion_y_excluye_eliminados(self):
        with patch("unificado.bandeja.render_template", return_value="ok") as plantilla:
            _, conexiones = self.pedir("GET", "/Svial", uf="TRANSVERSAL")
        sql, parametros = conexiones[0].consultas[0]
        self.assertIn("d.eliminado = 0", sql)
        self.assertIn("m.UF IN (?, ?)", sql)
        self.assertEqual(sorted(str(uf) for uf in parametros), ["10", "16"])
        self.assertEqual(set(plantilla.call_args.kwargs),
                         {"registros", "titulo_modulo", "tipo_modulo", "modulo", "modulo_config", "catalogos_evento"})

    def test_detalle_oculta_adjuntos_laborales_fuera_de_rrll(self):
        respuesta, _ = self.pedir("GET", "/Mtto/detalle/7", caso(), permisos=["Ingresar_modulo__mtto"])
        datos = respuesta.get_json()
        self.assertEqual(set(datos), {"registro", "oper", "mtto", "svial", "laboral", "archivos",
                                      "archivos_mtto", "archivos_svial", "archivos_laboral"})
        self.assertEqual(set(datos["laboral"]), {"eventos", "estado", "pendientes"})
        self.assertEqual(datos["archivos_laboral"], [])

    # Adjuntos por identificador ------------------------------------------------------
    def test_descarga_de_otro_modulo_se_niega_sin_consultar(self):
        for tipo, permisos in (("laboral", ["Ingresar_modulo__mtto"]), ("reparaciones", ["Ingresar_modulo__oper"])):
            with self.subTest(tipo=tipo):
                respuesta, conexiones = self.pedir("GET", f"/archivo/9?tipo={tipo}", permisos=permisos)
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(conexiones, [])

    def test_descarga_busca_solo_por_id_y_cierra_la_conexion(self):
        respuesta, conexiones = self.pedir("GET", "/archivo/9?tipo=mtto&FilePath=C:/Windows/win.ini")
        self.assertEqual(respuesta.status_code, 404)
        sql, parametros = conexiones[0].consultas[0]
        # Todos los adjuntos del caso están en una tabla; el tipo filtra por módulo.
        self.assertIn("FROM flota.table_damage_files as f", sql)
        self.assertEqual(parametros, [9, "Mantenimiento"])
        self.assertEqual(conexiones[0].eventos, ["cursor.close", "close"])

    def test_modelo_de_adjuntos_rechaza_tipos_fuera_de_la_lista(self):
        cursor = Conexion({}).cursor()
        with self.assertRaises(ValueError):
            modelo_archivos.buscar_adjunto(cursor, "usuario", 1)
        self.assertEqual(cursor.conexion.consultas, [])

    def test_guardar_adjunto_falla_revierte_y_borra_el_archivo(self):
        carpeta = Path(tempfile.mkdtemp(prefix="unificado-adjuntos-"))
        with patch.dict(backend_unificado.UPLOAD_FOLDERS, {"Mtto": carpeta}):
            respuesta, conexiones = self.pedir(
                "POST", "/Mtto/agregar_mtto", caso(), falla="INSERT INTO flota.table_damage_files",
                data={"Id_damage_to_fleet": "7", "Costo": "1",
                      "archivos": (io.BytesIO(b"%PDF-1.4\n%%EOF"), "ot.pdf")},
                content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(conexiones[-1].eventos, ["rollback", "cursor.close", "close"])
        self.assertEqual([p for p in carpeta.rglob("*") if p.is_file()], [])


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF no está instalado")
class CsrfDelModuloUnificadoTests(unittest.TestCase):
    def test_formularios_sin_token_se_rechazan_antes_de_tocar_la_base(self):
        import backend_interfaz
        app = backend_interfaz.Interfaz
        sesion_valida = Conexion({"": [(1, "10", 0, 7, "ana.p")]})  # Activo, UF, Cambio_password_obligatorio
        with patch.dict(app.config, {"WTF_CSRF_ENABLED": True, "TESTING": True}), \
                patch.object(backend_interfaz, "_validar_esquema_una_vez_por_proceso", return_value=None), \
                patch.object(backend_interfaz, "connect", return_value=sesion_valida), \
                patch.object(backend_unificado, "connect") as conexion_del_modulo:
            cliente = app.test_client()
            with cliente.session_transaction() as sesion:
                sesion["usuario"], sesion["UF"], sesion["permisos"] = "ana.p", "10", list(TODOS)
            for url in ("/Mtto/agregar_mtto", "/laboral/agregar_rl", "/Operaciones/reabrir_evento/7"):
                with self.subTest(url=url):
                    self.assertEqual(cliente.post(url, data={"Id_damage_to_fleet": "7"}).status_code, 400)
        conexion_del_modulo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
