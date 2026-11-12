"""MVC-3: consultas compartidas, limites de acceso y ausencia de copias SQL."""
import ast
import re
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from modelos import casos, historico_danos, historico_movil, operaciones, laboral, flota
from modelos.detalle_historicos import CAMPOS_MOVIL
from repositories.sesiones import sesion_bd


class ArquitecturaAccesoTests(unittest.TestCase):
    def test_controladores_no_abren_conexiones_directamente(self):
        archivos = list((RAIZ / "backend").glob("backend_*.py"))
        archivos += list((RAIZ / "backend" / "unificado").glob("*.py"))
        for archivo in archivos:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Call):
                    nombre = getattr(nodo.func, "attr", getattr(nodo.func, "id", ""))
                    self.assertNotEqual(nombre, "connect", f"{archivo}:{nodo.lineno}")

    def test_sql_fuera_de_controladores_y_repositories_de_sesion(self):
        for archivo in (RAIZ / "backend").rglob("*.py"):
            if "modelos" in archivo.parts or archivo.name in {"schema_migrations.py", "manage_db.py"}:
                continue
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Call):
                    self.assertNotEqual(getattr(nodo.func, "attr", ""), "execute", str(archivo))

    def test_no_hay_consultas_sql_identicas_en_distintos_modelos(self):
        consultas = defaultdict(set)
        for archivo in (RAIZ / "backend" / "modelos").glob("*.py"):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Call) or getattr(nodo.func, "attr", "") != "execute" or not nodo.args:
                    continue
                argumento = nodo.args[0]
                if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
                    texto = argumento.value
                elif isinstance(argumento, ast.JoinedStr):
                    texto = "".join(parte.value if isinstance(parte, ast.Constant)
                                    else "{" + ast.unparse(parte.value) + "}" for parte in argumento.values)
                else:
                    continue
                clave = re.sub(r"\s+", " ", texto).strip().lower()
                consultas[clave].add(archivo.name)
        duplicadas = {sql: sorted(archivos) for sql, archivos in consultas.items() if len(archivos) > 1}
        self.assertEqual(duplicadas, {})

    def test_consultas_compartidas_son_la_misma_funcion(self):
        self.assertIs(historico_danos.buscar_caso, casos.buscar_caso_completo)
        self.assertIs(historico_movil.buscar_dano, casos.buscar_caso_completo)
        self.assertIs(operaciones.buscar_caso_completo, casos.buscar_caso_completo)
        self.assertIs(operaciones.crear_cierre_laboral, laboral.crear_cierre)
        self.assertIs(operaciones.buscar_nombre_del_operador, flota.buscar_fila_del_conductor)

    def test_sesion_abre_una_vez_y_cierra_si_falla(self):
        conexion = MagicMock()
        conectar = MagicMock(return_value=conexion)
        with self.assertRaisesRegex(ValueError, "simulado"):
            with sesion_bd(conectar, transaccional=True):
                raise ValueError("simulado")
        conectar.assert_called_once_with()
        conexion.rollback.assert_called_once_with()
        conexion.close.assert_called_once_with()
        conexion.commit.assert_not_called()


class CursorDetalle:
    """Resultados representativos del detalle; no requiere SQL Server."""
    def execute(self, sql, parametros):
        self.parametros = parametros
        if "FROM proceso.v_BD6_table_info_oper" in sql:
            fila = dict(Observaciones_operaciones="oper", rev_error="SI",
                        observaciones_correctivos="ajuste", responsabilidad_operador="SI",
                        conciliacion="SI", costo_oper=150, Fecha_registro="fecha",
                        Usuario_registro_oper="operador")
        elif "FROM proceso.v_BD6_table_info_svial" in sql:
            fila = dict(Observaciones_svial="svial", valor_conciliado_terceros=10,
                        conciliado_a_favor="empresa", Fecha_registro="fecha",
                        Usuario_registro_svial="seguridad")
        elif "FROM proceso.v_BD6_table_info_mtto" in sql:
            fila = dict(Costo=200, observaciones="mtto", dano_adicional="NO",
                        Fecha_registro="fecha", Usuario_registro_mtto="mantenimiento")
        else:
            fila = dict(Id=1, TipoArchivo=parametros[0], FileName="foto.png", Fecha_subida="fecha")
        self.description = [(campo,) for campo in fila]
        self.fila = tuple(fila.values())

    def fetchone(self):
        return self.fila

    def fetchall(self):
        return [self.fila]


class DetalleHistoricosTests(unittest.TestCase):
    def test_movil_conserva_columnas_y_archivos_sin_datos_laborales(self):
        datos = historico_movil.gestiones_y_archivos_del_dano(CursorDetalle(), 7)
        self.assertEqual(set(datos), {"oper", "svial", "mtto", "archivos"})
        for modulo, campos in CAMPOS_MOVIL.items():
            self.assertEqual(set(datos[modulo]), set(campos))
        self.assertEqual(datos["mtto"]["Costo"], 200)
        self.assertEqual(datos["archivos"][0]["TipoArchivo"], "operaciones")

    def test_danos_conserva_campos_completos_y_secciones_adicionales(self):
        datos = historico_danos.buscar_gestiones_y_adjuntos(CursorDetalle(), 7)
        self.assertEqual(datos["oper"]["costo_oper"], 150)
        self.assertEqual(datos["mtto"]["Usuario_registro_mtto"], "mantenimiento")
        self.assertTrue({"laboral", "laboralm", "correcciones", "archivos_laboral",
                         "archivos_mtto", "archivos_svial"}.issubset(datos))

    def test_sin_gestiones_conserva_none_y_listas_vacias(self):
        cursor = MagicMock(description=[])
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        datos = historico_movil.gestiones_y_archivos_del_dano(cursor, 7)
        self.assertEqual(datos, dict(oper=None, svial=None, mtto=None, archivos=[]))

    def test_se_conservan_uf_eliminacion_y_ocultamiento_laboral(self):
        from flask import Flask
        import backend_historico_danos as danos
        import backend_historico_movil as movil
        app = Flask(__name__)
        app.secret_key = "mvc3-prueba"
        app.register_blueprint(danos.Historico_danos, url_prefix="/danos")
        app.register_blueprint(movil.Historico_movil, url_prefix="/movil")
        cliente = app.test_client()
        with cliente.session_transaction() as sesion:
            sesion.update(usuario="auditoria", UF="10", permisos=[
                "Ingresar_historico_danos", "Ingresar_danos_vs_reparaciones"])
        for modulo, modelo, consulta, detalle, url in (
            (danos, danos.modelo_historico, "buscar_caso", "buscar_gestiones_y_adjuntos", "/danos/detalle/7"),
            (movil, movil.modelo, "buscar_dano", "gestiones_y_archivos_del_dano", "/movil/detalle/7"),
        ):
            with patch.object(modulo, "connect", return_value=MagicMock()), \
                    patch.object(modelo, consulta, return_value={"UF": "16"}), \
                    patch.object(modelo, detalle) as cargar:
                self.assertEqual(cliente.get(url).status_code, 403)
                cargar.assert_not_called()
        with patch.object(movil, "connect", return_value=MagicMock()), \
                patch.object(movil.modelo, "buscar_dano", return_value={"UF": "10", "eliminado": 1}), \
                patch.object(movil.modelo, "gestiones_y_archivos_del_dano") as cargar:
            self.assertEqual(cliente.get("/movil/detalle/7").status_code, 404)
            cargar.assert_not_called()
        with patch.object(danos, "connect", return_value=MagicMock()), \
                patch.object(danos.modelo_historico, "buscar_caso", return_value={"UF": "10"}), \
                patch.object(danos.modelo_historico, "buscar_gestiones_y_adjuntos",
                             return_value={"archivos_laboral": [{"Id": 99}]}):
            self.assertEqual(cliente.get("/danos/detalle/7").get_json()["archivos_laboral"], [])


if __name__ == "__main__":
    unittest.main()
