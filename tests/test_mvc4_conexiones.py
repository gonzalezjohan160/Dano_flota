"""MVC-4: transacciones y cierre ante errores, sin conectarse a SQL Server."""
import sys
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from conexiones import conexion_bd


class Conexion:
    def __init__(self, falla=None):
        self.eventos = []
        self.falla = falla or set()
        self.cerrada = False

    def paso(self, nombre):
        self.eventos.append(nombre)
        if nombre in self.falla:
            raise RuntimeError(nombre)

    def cursor(self):
        self.paso("cursor")
        return self

    def commit(self):
        assert not self.cerrada
        self.paso("commit")

    def rollback(self):
        assert not self.cerrada, "rollback despues de cerrar"
        self.paso("rollback")

    def close(self):
        self.cerrada = True
        self.paso("close")


class ConexionTests(unittest.TestCase):
    def test_confirma_y_cierra(self):
        c = Conexion()
        with conexion_bd(c, transaccional=True):
            c.paso("escritura")
        self.assertEqual(c.eventos, ["escritura", "commit", "close"])

    def test_lectura_no_confirma(self):
        c = Conexion()
        with conexion_bd(c):
            pass
        self.assertEqual(c.eventos, ["close"])

    def test_error_de_commit_o_consulta_revierte_y_cierra(self):
        for fallo in ("consulta", "commit", "cursor"):
            c = Conexion({fallo})
            with self.subTest(fallo=fallo), self.assertRaisesRegex(RuntimeError, fallo):
                with conexion_bd(c, transaccional=True):
                    c.cursor()
                    c.paso("consulta")
            self.assertEqual(c.eventos[-2:], ["rollback", "close"])

    def test_fallo_de_rollback_y_cierre_no_oculta_error_original(self):
        c = Conexion({"rollback", "close"})
        with patch("conexiones.log"), self.assertRaisesRegex(ValueError, "original"):
            with conexion_bd(c, transaccional=True):
                raise ValueError("original")
        self.assertEqual(c.eventos, ["rollback", "close"])

    def test_error_al_cerrar_sin_otro_error_se_propaga(self):
        c = Conexion({"close"})
        with self.assertRaisesRegex(RuntimeError, "close"):
            with conexion_bd(c):
                pass

    def test_error_de_cierre_del_cursor_revierte_y_cierra_conexion(self):
        class Cursor:
            def close(self):
                raise RuntimeError("cursor.close")

        c = Conexion()
        with self.assertRaisesRegex(RuntimeError, "cursor.close"):
            with conexion_bd(c, transaccional=True), closing(Cursor()):
                pass
        self.assertEqual(c.eventos, ["rollback", "close"])

    def test_return_tambien_confirma_y_cierra(self):
        c = Conexion()

        def operacion():
            with conexion_bd(c, transaccional=True):
                return "ok"

        self.assertEqual(operacion(), "ok")
        self.assertEqual(c.eventos, ["commit", "close"])


class RutasUsuariosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        import backend_usuarios
        import backend_permisos_roles
        cls.app = Flask(__name__)
        cls.app.secret_key = "mvc4-prueba"
        cls.usuarios = backend_usuarios
        cls.permisos = backend_permisos_roles

    def test_usuarios_y_permisos_conservan_respuesta_si_falla_escritura(self):
        from flask import session
        from unittest.mock import MagicMock
        datos_crear = dict(Nombre="Ana", IDusuario="123", username="ana.p",
                           password="ClaveSegura2026", Email="ana@empresa.co", UF="10")
        casos = [
            (self.usuarios, self.usuarios.crear_usuario, datos_crear, "crear_usuario"),
            (self.usuarios, self.usuarios.editar_usuario,
             dict(IDusuario="123", Nombre="Ana"), "actualizar_usuario"),
            (self.permisos, self.permisos.forzar_cambio_password,
             dict(user_ids=["123", "456"]), "actualizar_obligacion_contrasena"),
        ]
        for modulo, vista, datos, escritura in casos:
            with self.subTest(vista=vista.__name__):
                c = Conexion()
                cursor = MagicMock()
                cursor.close.side_effect = lambda: c.paso("cursor.close")
                c.cursor = lambda: cursor
                modelo = modulo.modelo_usuarios
                with self.app.test_request_context("/", method="POST", data=datos):
                    session.update(usuario="auditoria", usuario_id=7, permisos=[
                        "Ingresar_crear_usuario", "Ingresar_asignar_permisos"])
                    with patch.object(modulo, "connect", return_value=c), \
                            patch.object(modelo, "existe_usuario", return_value=False), \
                            patch.object(modelo, "buscar_usuario_por_identificacion", return_value=("ana.p",)), \
                            patch.object(modelo, escritura, side_effect=RuntimeError("escritura")), \
                            patch.object(modulo, "logger"), \
                            patch.object(modulo, "flash") as aviso, \
                            patch.object(modulo, "render_template", return_value="formulario", create=True):
                        respuesta = vista()
                        self.assertIsNotNone(respuesta)
                        self.assertEqual(aviso.call_args.args[1], "error")
                self.assertEqual(c.eventos, ["cursor.close", "rollback", "close"])


if __name__ == "__main__":
    unittest.main()
