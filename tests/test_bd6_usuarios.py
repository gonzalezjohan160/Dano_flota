"""BD-6: autor numerico confiable, compatibilidad de sesion y escrituras."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from flask import Flask, session
from werkzeug.exceptions import Unauthorized
from backend_security import usuario_id_sesion


class UsuarioSesionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "bd6-pruebas"

    def test_autor_se_toma_del_id_interno_y_no_del_formulario(self):
        with self.app.test_request_context("/", method="POST", data={"usuario_id": "999", "Registrador": "otro"}):
            session.update(usuario="ana.p", usuario_id=7)
            self.assertEqual(usuario_id_sesion(), 7)

    def test_rechaza_identificadores_ausentes_textuales_o_booleanos(self):
        for valor in (None, "ana.p", "7", True, 0, -1):
            with self.subTest(valor=valor), self.app.test_request_context("/"):
                session.update(usuario="ana.p", usuario_id=valor)
                with self.assertRaises(Unauthorized):
                    usuario_id_sesion()

    def test_sesion_anterior_se_actualiza_sin_cerrar_sesion(self):
        import backend_interfaz as interfaz
        with interfaz.Interfaz.test_request_context("/interfaz"):
            session.update(usuario="anterior", usuario_id="anterior")
            with patch.object(interfaz, "connect", return_value=MagicMock()), \
                    patch.object(interfaz.modelo_autenticacion, "buscar_estado_de_sesion",
                                 return_value=(1, "10", 0, 7, "nombre_actual")) as estado, \
                    patch.object(interfaz, "cargar_permisos", return_value=[]) as permisos:
                self.assertIsNone(interfaz.proteger_rutas())
                self.assertEqual(estado.call_args.args[1], "anterior")
                self.assertEqual(permisos.call_args.args[0], 7)
            self.assertEqual(session["usuario_id"], 7)
            self.assertEqual(session["usuario"], "nombre_actual")


class EscriturasUsuarioTests(unittest.TestCase):
    def test_ocho_escrituras_referencian_usuario_id(self):
        from modelos import capturador, reparaciones, operaciones, mantenimiento, seguridad_vial, laboral, auditoria
        datos = {campo: "x" for campo in ("fecha_evento", "movil", "codigo", "nombre", "area", "ruta",
                 "direccion", "version_libre", "parte_afectada", "dano_ocasionado", "zona_dano",
                 "centro_operaciones", "fecha_registro", "zona_intervenida", "parte_intervenida", "costo")}
        datos["registrador"] = 7
        llamadas = [
            lambda c: capturador.crear_caso(c, datos),
            lambda c: reparaciones.crear_reparacion(c, datos),
            lambda c: operaciones.crear_gestion(c, 1, ("o", 7, "", "SI", "SI", "SI", 100)),
            lambda c: mantenimiento.crear_gestion(c, [1, 100, "NO", "o", 7]),
            lambda c: seguridad_vial.crear_gestion(c, [1, "o", 7, "empresa", 100]),
            lambda c: laboral.crear_cierre(c, 1, "CONCILIACIÓN", 100, 7),
            lambda c: laboral.registrar_seguimiento(c, 1, None, "COMPLETO", "o", 7, None),
            lambda c: auditoria.registrar_correccion(c, 1, "tabla", "campo", "a", "b", 7, None, "m"),
        ]
        for numero, llamada in enumerate(llamadas):
            with self.subTest(escritura=numero):
                cursor = MagicMock()
                cursor.fetchone.return_value = (1,)
                llamada(cursor)
                argumentos = cursor.execute.call_args.args
                self.assertIn("usuario_id", argumentos[0])
                self.assertNotIn("Usuario_registro", argumentos[0])
                self.assertNotIn("Usuario_Modifica", argumentos[0])
                self.assertNotIn("Registrador", argumentos[0])
                valores = argumentos[1] if isinstance(argumentos[1], (list, tuple)) else argumentos[1:]
                self.assertIn(7, valores)


class EsquemaUsuariosTests(unittest.TestCase):
    def conexion(self):
        from schema_migrations import REQUIRED_COLUMNS
        conexion = MagicMock()
        conexion.cursor.return_value.fetchall.return_value = [
            (c.schema, c.table, c.column, c.sql_type, c.max_length, c.nullable,
             f"(({c.default}))" if c.default is not None else None)
            for c in REQUIRED_COLUMNS
        ]
        return conexion

    def test_arranque_acepta_bits_not_null_y_las_ocho_referencias(self):
        from schema_migrations import validate_required_schema
        validate_required_schema(self.conexion())

    def test_arranque_rechaza_si_falta_usuario_id(self):
        from schema_migrations import validate_required_schema, SchemaValidationError
        conexion = self.conexion()
        filas = conexion.cursor.return_value.fetchall.return_value
        conexion.cursor.return_value.fetchall.return_value = [
            f for f in filas if not (f[1] == "table_info_oper" and f[2] == "usuario_id")]
        with self.assertRaisesRegex(SchemaValidationError, "falta proceso.table_info_oper.usuario_id"):
            validate_required_schema(conexion)


if __name__ == "__main__":
    unittest.main()
