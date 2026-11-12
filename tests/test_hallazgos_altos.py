"""Pruebas de regresión de los hallazgos altos y de los cambios preventivos.

Se ejecutan sin SQL Server: la conexión se reemplaza por una simulada que
registra las consultas.
"""
import importlib.util
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
# Las pruebas escriben su log aparte, no en backend/logs/app.log.
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
os.environ.setdefault("SECRET_KEY", "hallazgos-test-only")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-hallazgos-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))
sys.path.insert(0, str(PROJECT_DIR / "tests"))
from catalogos_de_prueba import parchar_catalogos  # noqa: E402
if "pyodbc" not in sys.modules and importlib.util.find_spec("pyodbc") is None:
    sys.modules["pyodbc"] = types.ModuleType("pyodbc")

CONSULTAS = []


class CursorSimulado:
    description = [("c",)]
    rowcount = 1

    def __init__(self, filas=None):
        self.filas = list(filas or [])

    def execute(self, sql, *args):
        CONSULTAS.append((sql, args))
        return self

    def fetchone(self):
        return self.filas.pop(0) if self.filas else None

    def fetchall(self):
        return []

    def nextset(self):
        return False

    def close(self):
        pass


class ConexionSimulada:
    def __init__(self, filas=None):
        self.filas = filas
        self.commits = 0

    def cursor(self):
        return CursorSimulado(self.filas)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


class CursorGlobal(CursorSimulado):
    """Estado del usuario que consulta proteger_rutas en cada petición.

    Por defecto la base coincide con la sesión de la prueba; ESTADO_USUARIO
    permite simular que el usuario fue desactivado o cambiado en la base.
    """
    def execute(self, sql, *args):
        self.sql = sql
        return self

    def fetchone(self):
        from flask import session
        if ESTADO_USUARIO:
            return ESTADO_USUARIO.get("fila")
        return (1, session.get("UF"), 0)

    def fetchall(self):
        from flask import session
        if ESTADO_USUARIO:
            return [(p,) for p in ESTADO_USUARIO.get("permisos", [])]
        return [(p,) for p in session.get("permisos", [])]


ESTADO_USUARIO = {}


class ConexionGlobal(ConexionSimulada):
    def cursor(self):
        return CursorGlobal()


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF no está instalado")
class HallazgosAltosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backend_interfaz
        cls.interfaz = backend_interfaz
        cls.app = backend_interfaz.Interfaz
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.app.config["PROPAGATE_EXCEPTIONS"] = False
        cls.modulos = {n: m for n, m in sys.modules.items()
                       if n.startswith("backend_") and n != "backend_interfaz" and hasattr(m, "connect")}

    def setUp(self):
        CONSULTAS.clear()
        ESTADO_USUARIO.clear()
        self.interfaz.limiter.reset()
        self.parches = [
            patch.object(self.interfaz, "_validar_esquema_una_vez_por_proceso", return_value=None),
            patch.object(self.interfaz, "connect", side_effect=ConexionGlobal),
        ] + [patch.object(m, "connect", side_effect=ConexionSimulada) for m in self.modulos.values()]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def cliente(self, permisos=(), uf="10"):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s.update(usuario="prueba", usuario_id="prueba", UF=uf, permisos=list(permisos))
        return c

    # M-08: cookie de sesión con Secure y HTTPS reconocido detrás de nginx ----------
    def test_cookie_de_sesion_lleva_secure(self):
        from flask import session
        with self.app.test_request_context():
            session["usuario"] = "prueba"
            respuesta = self.app.make_response("")
            self.app.session_interface.save_session(self.app, session, respuesta)
        cookie = respuesta.headers.get("Set-Cookie", "")
        for marca in ("Secure", "HttpOnly", "SameSite=Lax"):
            self.assertIn(marca, cookie)

    def test_proxyfix_reconoce_https_de_nginx(self):
        from werkzeug.test import EnvironBuilder
        proxy = self.app.wsgi_app
        recibido = {}
        original = proxy.app
        proxy.app = lambda environ, start_response: recibido.update(environ) or []
        try:
            environ = EnvironBuilder(headers={"X-Forwarded-Proto": "https",
                                              "X-Forwarded-For": "203.0.113.7"}).get_environ()
            proxy(environ, lambda *a: None)
        finally:
            proxy.app = original
        self.assertEqual(recibido["wsgi.url_scheme"], "https")
        self.assertEqual(recibido["REMOTE_ADDR"], "203.0.113.7")

    # M-01: desactivar o cambiar permisos/UF aplica a la sesión ya abierta ---------
    def test_usuario_desactivado_pierde_la_sesion_abierta(self):
        c = self.cliente(["Ingresar_danos_vs_reparaciones"])
        ESTADO_USUARIO.update(fila=(0, "10", 0))
        r = c.get("/Historico_movil/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/", r.headers["Location"])
        with c.session_transaction() as s:
            self.assertNotIn("usuario", s)

    def test_usuario_eliminado_pierde_la_sesion_abierta(self):
        c = self.cliente(["Ingresar_danos_vs_reparaciones"])
        ESTADO_USUARIO.update(fila=None)
        c.get("/Historico_movil/")
        with c.session_transaction() as s:
            self.assertNotIn("usuario", s)

    def test_permiso_retirado_aplica_sin_volver_a_iniciar_sesion(self):
        c = self.cliente(["Ingresar_danos_vs_reparaciones"])
        ESTADO_USUARIO.update(fila=(1, "10", 0), permisos=[])
        # Responde 403 (sin redirigir); la sesión sigue abierta sin el permiso.
        r = c.get("/Historico_movil/")
        self.assertEqual(r.status_code, 403)
        with c.session_transaction() as s:
            self.assertEqual(s["permisos"], [])

    def test_cambio_de_uf_aplica_sin_volver_a_iniciar_sesion(self):
        c = self.cliente(["Ingresar_danos_vs_reparaciones"], uf="10")
        ESTADO_USUARIO.update(fila=(1, "16", 0), permisos=["Ingresar_danos_vs_reparaciones"])
        c.get("/Historico_movil/")
        with c.session_transaction() as s:
            self.assertEqual(s["UF"], "16")

    def test_usuario_desactivado_no_puede_cambiar_password(self):
        c = self.cliente()
        ESTADO_USUARIO.update(fila=(0, "10", 0))
        c.post("/Profile/cambiar-password")
        with c.session_transaction() as s:
            self.assertNotIn("usuario", s)

    # M-14: carga común del caso con UF, eliminado y cerrado -----------------------
    def con_caso(self, uf="10", eliminado=0, cerrado=0):
        import backend_unificado
        fila = (uf, eliminado, cerrado)
        return patch.object(backend_unificado, "connect",
                            side_effect=lambda: ConexionSimulada([fila]))

    def gestionar(self, **estado):
        with self.con_caso(**estado):
            return self.cliente(["Ingresar_modulo__mtto"]).post(
                "/Mtto/agregar_mtto", data={"Id_damage_to_fleet": "1"})

    def test_gestion_sobre_caso_cerrado_responde_409(self):
        r = self.gestionar(cerrado=1)
        self.assertEqual(r.status_code, 409)
        self.assertIn("reabrirse", r.get_json()["message"])
        self.assertFalse(any(s.strip().startswith(("INSERT", "UPDATE")) for s, _ in CONSULTAS))

    def test_gestion_sobre_caso_eliminado_responde_404(self):
        r = self.gestionar(eliminado=1)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(any(s.strip().startswith(("INSERT", "UPDATE")) for s, _ in CONSULTAS))

    def test_gestion_sobre_caso_de_otra_uf_se_niega(self):
        r = self.gestionar(uf="16")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any(s.strip().startswith(("INSERT", "UPDATE")) for s, _ in CONSULTAS))

    def test_gestion_sin_id_de_caso_se_rechaza(self):
        r = self.cliente(["Ingresar_modulo__mtto"]).post("/Mtto/agregar_mtto", data={})
        self.assertEqual(r.status_code, 400)

    def test_detalle_de_caso_eliminado_no_se_muestra(self):
        with self.con_caso(eliminado=1):
            r = self.cliente(["Ingresar_modulo__mtto"]).get("/Mtto/detalle/1")
        self.assertEqual(r.status_code, 404)

    def test_detalle_de_caso_cerrado_si_se_consulta(self):
        import backend_unificado
        with self.con_caso(cerrado=1), \
                patch.object(backend_unificado, "verificar_acceso_uf_caso",
                             wraps=backend_unificado.verificar_acceso_uf_caso) as verif:
            self.cliente(["Ingresar_modulo__mtto"]).get("/Mtto/detalle/1")
        verif.assert_called_once_with(1)  # sin exigir caso abierto

    def test_editar_evento_cerrado_responde_409(self):
        with self.con_caso(cerrado=1):
            r = self.cliente(["Ingresar_modulo__oper", "Corregir_info_oper"]).post(
                "/Operaciones/actualizar_evento/1",
                json={"evento": {"Zona_dano": "TECHO"}, "motivo_modificacion": "x"})
        self.assertEqual(r.status_code, 409)

    # M-02: el registrador sale de la sesión, no del formulario -------------------
    def valores_escritos(self):
        return [v for sql, args in CONSULTAS if sql.strip().startswith(("INSERT", "UPDATE"))
                for a in args for v in (a if isinstance(a, (list, tuple)) else [a])]

    def test_gestion_ignora_usuario_del_formulario(self):
        import backend_unificado
        # 1.ª conexión: caso abierto de la UF; luego, sin gestión previa de Mtto.
        conexiones = iter([ConexionSimulada([("10", 0, 0)])])
        with patch.object(backend_unificado, "connect",
                          side_effect=lambda: next(conexiones, None) or ConexionSimulada([])):
            self.cliente(["Ingresar_modulo__mtto"]).post("/Mtto/agregar_mtto", data={
                "Id_damage_to_fleet": "1", "Usuario_registro_oper": "otra_persona"})
        escritos = self.valores_escritos()
        self.assertTrue(escritos, "la gestión debe escribir en la base")
        self.assertIn("prueba", escritos)
        self.assertNotIn("otra_persona", escritos)

    def test_capturador_y_reparaciones_no_leen_el_usuario_del_formulario(self):
        for modulo, campo in (("backend_capturador.py", "Inspector"), ("backend_reparaciones.py", "Usuario")):
            fuente = (PROJECT_DIR / "backend" / modulo).read_text(encoding="utf-8")
            self.assertNotIn(f"request.form.get('{campo}')", fuente, modulo)
            self.assertIn("registrador = session.get('usuario')", fuente, modulo)
        fuente = (PROJECT_DIR / "backend" / "backend_unificado.py").read_text(encoding="utf-8")
        self.assertNotIn('request.form.get("Usuario_registro_oper")', fuente)

    # B-15: el 503 por esquema incompatible no muestra detalles al cliente ---------
    def test_503_de_esquema_es_generico_y_detalle_va_al_log(self):
        detalle = ("Esquema SQL Server incompatible: dbo.Table_usuarios.Cambio_password_obligatorio "
                   "... Aplique las migraciones pendientes con `python manage_db.py migrate`")
        with patch.object(self.interfaz, "_validar_esquema_una_vez_por_proceso", return_value=detalle):
            r = self.app.test_client().get("/")
        self.assertEqual(r.status_code, 503)
        cuerpo = r.get_data(as_text=True)
        self.assertIn("Servicio no disponible temporalmente", cuerpo)
        for fuga in ("Table_usuarios", "Cambio_password", "manage_db", "migrate", "Esquema"):
            self.assertNotIn(fuga, cuerpo)

    def test_esquema_incompatible_registra_el_detalle_en_el_log(self):
        from schema_migrations import SchemaValidationError
        validar_original = self.parches[0].temp_original  # setUp lo reemplaza por un simulado
        self.interfaz._SCHEMA_VALIDATION_PID = None
        try:
            with patch.object(self.interfaz, "validate_required_schema",
                              side_effect=SchemaValidationError("dbo.Tabla_x.columna_y falta")), \
                    patch.object(self.interfaz.logger, "error") as log:
                error = validar_original()
        finally:
            self.interfaz._SCHEMA_VALIDATION_PID = None
        self.assertIn("dbo.Tabla_x.columna_y", str(log.call_args))
        self.assertIn("dbo.Tabla_x.columna_y", error)

    # M-11: cabeceras de seguridad en todas las respuestas ------------------------
    CABECERAS_SEGURIDAD = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Frame-Options": "SAMEORIGIN",
    }

    def assert_cabeceras_seguridad(self, r, url):
        for cabecera, valor in self.CABECERAS_SEGURIDAD.items():
            self.assertEqual(r.headers.get(cabecera), valor, f"{cabecera} en {url}")
        self.assertIn("frame-ancestors 'self'", r.headers.get("Content-Security-Policy", ""), url)

    def test_cabeceras_de_seguridad_en_paginas_publicas_y_privadas(self):
        import backend_login
        with patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([])):
            for url in ("/", "/forgot-password", "/static/Style/Style_login.css", "/no-existe"):
                self.assert_cabeceras_seguridad(self.app.test_client().get(url), url)
        r = self.cliente(["Ingresar_dashboard"]).get("/interfaz")
        self.assert_cabeceras_seguridad(r, "/interfaz")

    def test_cabeceras_de_seguridad_en_503(self):
        with patch.object(self.interfaz, "_validar_esquema_una_vez_por_proceso", return_value="x"):
            r = self.app.test_client().get("/")
        self.assertEqual(r.status_code, 503)
        self.assert_cabeceras_seguridad(r, "503")

    def test_adjuntos_conservan_x_frame_options_deny(self):
        from flask import Response
        from attachment_security import apply_attachment_headers
        with self.app.test_request_context("/archivo/1"):
            r = apply_attachment_headers(Response("x"))
            r = self.app.process_response(r)
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["Referrer-Policy"], "strict-origin-when-cross-origin")

    # M-18: un fallo de conexión al validar el esquema no se guarda en caché -------
    def validar_real(self):
        """La validación real (setUp la reemplaza por un simulado), con caché limpia."""
        self.interfaz._SCHEMA_VALIDATION_PID = None
        self.interfaz._SCHEMA_VALIDATION_ERROR = None
        self.interfaz._SCHEMA_FALLO_TRANSITORIO = None
        self.addCleanup(setattr, self.interfaz, "_SCHEMA_VALIDATION_PID", None)
        self.addCleanup(setattr, self.interfaz, "_SCHEMA_FALLO_TRANSITORIO", None)
        return self.parches[0].temp_original

    def test_base_caida_y_luego_disponible_se_recupera_sin_reiniciar(self):
        validar = self.validar_real()
        intentos = iter([ConnectionError("SQL Server no responde"), None])

        def conectar():
            fallo = next(intentos)
            if fallo:
                raise fallo
            return ConexionSimulada()

        with patch.object(self.interfaz, "connect", side_effect=conectar), \
                patch.object(self.interfaz, "validate_required_schema"), \
                patch.object(self.interfaz, "_validar_esquema_una_vez_por_proceso", validar):
            c = self.app.test_client()
            self.assertEqual(c.get("/").status_code, 503)   # 1.ª petición: base caída
            self.assertNotEqual(c.get("/").status_code, 503)  # 2.ª: base disponible

    def test_hilos_que_esperaban_comparten_el_mismo_intento(self):
        import threading
        import time as reloj
        validar = self.validar_real()
        intentos = []

        def conectar_lento():
            intentos.append(1)
            reloj.sleep(0.3)
            raise ConnectionError("SQL Server no responde")

        resultados = []
        with patch.object(self.interfaz, "connect", side_effect=conectar_lento):
            hilos = [threading.Thread(target=lambda: resultados.append(validar())) for _ in range(4)]
            inicio = reloj.monotonic()
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
            duracion = reloj.monotonic() - inicio
        self.assertEqual(len(intentos), 1)          # un solo intento de conexión
        self.assertLess(duracion, 0.9)              # no 4 esperas seguidas
        self.assertTrue(all(resultados))

    def test_exito_se_guarda_en_cache(self):
        validar = self.validar_real()
        with patch.object(self.interfaz, "connect", side_effect=ConexionSimulada) as conectar, \
                patch.object(self.interfaz, "validate_required_schema"):
            self.assertIsNone(validar())
            self.assertIsNone(validar())
        self.assertEqual(conectar.call_count, 1)

    def test_esquema_incompatible_se_guarda_en_cache(self):
        from schema_migrations import SchemaValidationError
        validar = self.validar_real()
        with patch.object(self.interfaz, "connect", side_effect=ConexionSimulada) as conectar, \
                patch.object(self.interfaz, "validate_required_schema",
                             side_effect=SchemaValidationError("falta columna")):
            self.assertIn("falta columna", validar())
            self.assertIn("falta columna", validar())
        self.assertEqual(conectar.call_count, 1)  # no se reintenta: requiere migrar y reiniciar

    def test_fallo_inesperado_al_inspeccionar_se_reintenta(self):
        validar = self.validar_real()
        with patch.object(self.interfaz, "connect", side_effect=ConexionSimulada) as conectar, \
                patch.object(self.interfaz, "validate_required_schema",
                             side_effect=[RuntimeError("conexión cortada"), None]):
            self.assertIsNotNone(validar())
            self.assertIsNone(validar())
        self.assertEqual(conectar.call_count, 2)

    # B-13: conexión con timeout corto y 503 genérico cuando la base no responde ---
    def test_connect_usa_timeout_corto_y_error_propio(self):
        import config
        import pyodbc
        with patch.object(config.pyodbc, "connect",
                          side_effect=pyodbc.OperationalError("HYT00", "Login timeout expired")) as conectar:
            with self.assertRaises(config.BaseDatosNoDisponible):
                config.connect()
        self.assertEqual(conectar.call_args.kwargs["timeout"], 3)

    def test_base_no_disponible_en_una_vista_responde_503_generico(self):
        from config import BaseDatosNoDisponible
        import backend_historico_movil
        with patch.object(backend_historico_movil, "connect",
                          side_effect=BaseDatosNoDisponible("SQL Server 10.0.0.5 no responde")):
            r = self.cliente(["Ingresar_danos_vs_reparaciones"]).get("/Historico_movil/")
        self.assertEqual(r.status_code, 503)
        cuerpo = r.get_data(as_text=True)
        self.assertIn("Servicio no disponible temporalmente", cuerpo)
        self.assertNotIn("10.0.0.5", cuerpo)

    def test_base_no_disponible_al_validar_sesion_responde_503(self):
        from config import BaseDatosNoDisponible
        with patch.object(self.interfaz, "connect", side_effect=BaseDatosNoDisponible("x")):
            r = self.cliente(["Ingresar_danos_vs_reparaciones"]).get("/Historico_movil/")
        self.assertEqual(r.status_code, 503)
        self.assertIn("Servicio no disponible temporalmente", r.get_data(as_text=True))

    # B-14: la conexión a SQL Server valida el certificado ------------------------
    def cadena_de_conexion(self, valor):
        import config
        with patch.object(config, "DB_TRUST_SERVER_CERTIFICATE", config.leer_trust_server_certificate(valor)), \
                patch.object(config.pyodbc, "connect") as conectar:
            config.connect()
        return conectar.call_args.args[0]

    def test_por_defecto_valida_el_certificado(self):
        cadena = self.cadena_de_conexion(None)
        self.assertIn("Encrypt=yes;", cadena)
        self.assertIn("TrustServerCertificate=no;", cadena)

    def test_solo_yes_explicito_desactiva_la_validacion(self):
        self.assertIn("TrustServerCertificate=yes;", self.cadena_de_conexion(" YES "))
        for valor in ("", "no", "si", "true", "1"):
            self.assertIn("TrustServerCertificate=no;", self.cadena_de_conexion(valor), valor)

    # M-15: /interfaz lleva a la primera pantalla permitida; 403/404 sin redirigir --
    def test_interfaz_lleva_a_la_primera_pantalla_permitida(self):
        casos = (
            (["Ingresar_dashboard", "Ingresar_captur_danos"], "/Dashboard/"),
            (["Ingresar_captur_danos"], "/Capturador/"),
            (["Ingresar_modulo__mtto", "Ingresar_danos_vs_reparaciones"], "/Mtto"),
            (["Ingresar_modulo__laboral"], "/laboral"),
            ([], "/Profile/"),
        )
        for permisos, destino in casos:
            r = self.cliente(permisos).get("/interfaz")
            self.assertEqual(r.status_code, 302, permisos)
            self.assertEqual(r.headers["Location"], destino, permisos)

    def test_solo_capturador_no_entra_en_bucle(self):
        c = self.cliente(["Ingresar_captur_danos"])
        visitadas = []
        url = "/interfaz"
        for _ in range(5):
            r = c.get(url)
            visitadas.append(url)
            if r.status_code != 302:
                break
            url = r.headers["Location"]
        self.assertNotEqual(r.status_code, 302, f"bucle de redirecciones: {visitadas}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(url, "/Capturador/")

    def test_403_en_navegacion_muestra_pagina_propia(self):
        r = self.cliente(["Ingresar_captur_danos"]).get("/Dashboard/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Acceso no permitido", r.get_data(as_text=True))

    def test_403_y_404_en_ajax_responden_json(self):
        cabeceras = {"Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"}
        with self.con_caso(uf="16"):
            r = self.cliente(["Ingresar_modulo__mtto"]).get("/Mtto/detalle/1", headers=cabeceras)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["status"], "error")
        r = self.cliente(["Ingresar_modulo__mtto"]).get("/no-existe", headers=cabeceras)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["status"], "error")

    def test_sin_sesion_los_errores_llevan_al_login(self):
        r = self.app.test_client().get("/no-existe")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/")

    # M-09: si algo falla antes del commit, no queda registro ni archivos en disco --
    def png_valido(self):
        import io as _io
        from PIL import Image
        buffer = _io.BytesIO()
        Image.new("RGB", (4, 4), "red").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def archivos_en(self, carpeta):
        carpeta = Path(carpeta)
        return sorted(p for p in carpeta.rglob("*") if p.is_file()) if carpeta.exists() else []

    def enviar_con_fallo_en_commit(self, url, permisos, datos, carpeta):
        import backend_unificado

        class ConexionQueFalla(ConexionSimulada):
            def commit(self):
                raise RuntimeError("fallo simulado al confirmar")

        rollbacks = []

        class ConexionRegistrada(ConexionQueFalla):
            def rollback(self):
                rollbacks.append(1)

        conexiones = iter([ConexionSimulada([("10", 0, 0)])])
        antes = self.archivos_en(carpeta)
        with patch.object(backend_unificado, "connect",
                          side_effect=lambda: next(conexiones, None) or ConexionRegistrada()):
            datos = dict(datos, archivos=(self.png_valido(), "foto.png"))
            r = self.cliente(permisos).post(url, data=datos, content_type="multipart/form-data")
        self.assertEqual(self.archivos_en(carpeta), antes, "quedaron archivos huérfanos en disco")
        self.assertTrue(rollbacks, "no se hizo rollback")
        return r

    def test_mtto_falla_al_confirmar_no_deja_archivos(self):
        from config import UPLOAD_FOLDERS
        r = self.enviar_con_fallo_en_commit(
            "/Mtto/agregar_mtto", ["Ingresar_modulo__mtto"],
            {"Id_damage_to_fleet": "1"}, UPLOAD_FOLDERS["Mtto"])
        self.assertEqual(r.status_code, 500)

    def test_rrll_falla_al_confirmar_no_deja_archivos_y_responde_error(self):
        from config import UPLOAD_FOLDERS
        r = self.enviar_con_fallo_en_commit(
            "/laboral/agregar_rl", ["Ingresar_modulo__laboral"],
            {"Id_damage_to_fleet": "1", "observaciones_1": "x", "Pendiente_proceso": "COMPLETO"},
            UPLOAD_FOLDERS["laboral"])
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json()["status"], "error")

    def test_rrll_sin_datos_obligatorios_responde_400(self):
        with self.con_caso():
            r = self.cliente(["Ingresar_modulo__laboral"]).post(
                "/laboral/agregar_rl", data={"Id_damage_to_fleet": "1"})
        self.assertEqual(r.status_code, 400)

    # B-08: valores en pesos inválidos responden 400, sin tocar la base -----------
    def test_leer_valor_monetario(self):
        from backend_unificado import leer_valor_monetario
        self.assertEqual(leer_valor_monetario("1.500.000", "x"), 1500000)
        self.assertEqual(leer_valor_monetario("$ 2,000", "x"), 2000)
        self.assertEqual(leer_valor_monetario(" 350000 ", "x"), 350000)
        self.assertIsNone(leer_valor_monetario(None, "x"))
        self.assertIsNone(leer_valor_monetario("", "x"))
        for invalido in ("abc", "12a", "-500", "1e6", "１２", "9223372036854775808"):
            with self.assertRaises(ValueError, msg=invalido):
                leer_valor_monetario(invalido, "x")

    def test_valor_conciliado_invalido_responde_400_en_cada_modulo(self):
        casos = (
            ("/Operaciones/agregar_oper", ["Ingresar_modulo__oper"],
             {"observaciones_1": "x", "costo_supera_2m": "NO", "responsabilidad_operador": "SI",
              "conciliacion": "SI", "valor_conciliado_oper": "abc"}),
            ("/Operaciones/agregar_oper", ["Ingresar_modulo__oper"],
             {"observaciones_1": "x", "costo_supera_2m": "NO", "costo_valor": "mil"}),
            ("/Svial/agregar_svial", ["Ingresar_modulo__svial"],
             {"Observaciones_svial": "x", "valor_conciliado_terceros": "abc"}),
            ("/Mtto/agregar_mtto", ["Ingresar_modulo__mtto"], {"Costo": "un millón"}),
            ("/laboral/agregar_rl", ["Ingresar_modulo__laboral"],
             {"observaciones_1": "x", "Pendiente_proceso": "COMPLETO", "Costo": "abc"}),
        )
        for url, permisos, datos in casos:
            CONSULTAS.clear()
            with self.con_caso():
                r = self.cliente(permisos).post(url, data=dict(datos, Id_damage_to_fleet="1"))
            self.assertEqual(r.status_code, 400, f"{url} {datos}")
            self.assertIn("número entero", r.get_json()["message"], url)
            escrituras = [sql for sql, _ in CONSULTAS if sql.strip().startswith(("INSERT", "UPDATE"))]
            self.assertEqual(escrituras, [], url)

    def test_valor_con_separadores_se_guarda_como_numero(self):
        import backend_unificado
        conexiones = iter([ConexionSimulada([("10", 0, 0)])])
        with patch.object(backend_unificado, "connect",
                          side_effect=lambda: next(conexiones, None) or ConexionSimulada([])):
            self.cliente(["Ingresar_modulo__mtto"]).post(
                "/Mtto/agregar_mtto", data={"Id_damage_to_fleet": "1", "Costo": "1.250.000"})
        self.assertIn(1250000, self.valores_escritos())

    # B-07: fechas mal formadas responden 400 en las tres pantallas ----------------
    PANTALLAS_CON_FECHAS = (
        ("/Historico_danos/", ["Ingresar_historico_danos"]),
        ("/Historico_danos/exportar_excel", ["Ingresar_historico_danos"]),
        ("/Historico_movil/", ["Ingresar_danos_vs_reparaciones"]),
        ("/Historico_movil/exportar_excel", ["Ingresar_danos_vs_reparaciones"]),
        ("/Dashboard/", ["Ingresar_dashboard"]),
    )

    def test_fechas_mal_formadas_responden_400(self):
        for url, permisos in self.PANTALLAS_CON_FECHAS:
            for consulta in ("fecha_inicio=abc", "fecha_fin=2026-13-45", "fecha_inicio=01/10/2026",
                             "fecha_inicio=2026-10-10&fecha_fin=2026-10-01"):
                CONSULTAS.clear()
                r = self.cliente(permisos).get(f"{url}?{consulta}")
                self.assertEqual(r.status_code, 400, f"{url}?{consulta}")
                self.assertIn("fecha", r.get_data(as_text=True).lower(), f"{url}?{consulta}")
                self.assertEqual(CONSULTAS, [], f"{url}?{consulta} no debe consultar la base")

    def test_filtro_f_fecha_del_historico_de_danos(self):
        r = self.cliente(["Ingresar_historico_danos"]).get("/Historico_danos/?f_fecha=abc")
        self.assertEqual(r.status_code, 400)

    def test_fechas_validas_llegan_como_date_a_la_consulta(self):
        import datetime as dt
        self.cliente(["Ingresar_danos_vs_reparaciones"]).get(
            "/Historico_movil/?fecha_inicio=2026-01-01&fecha_fin=2026-01-31")
        parametros = [a for _, args in CONSULTAS for p in args
                      for a in (p if isinstance(p, (list, tuple)) else [p])]
        self.assertIn(dt.date(2026, 1, 1), parametros)
        self.assertIn(dt.date(2026, 2, 1), parametros)  # fin + 1 día: incluye todo el 31

    def test_historico_movil_conserva_las_fechas_en_la_pantalla(self):
        import backend_historico_movil
        with patch.object(backend_historico_movil, "render_template", return_value="") as render, \
                patch.object(backend_historico_movil, "connect", side_effect=lambda: ConexionSimulada([(0,)])):
            self.cliente(["Ingresar_danos_vs_reparaciones"]).get(
                "/Historico_movil/?fecha_inicio=2026-01-01")
        filtros = render.call_args.kwargs["filtros"]
        self.assertEqual(filtros["fecha_inicio"], "2026-01-01")
        self.assertEqual(filtros["fecha_fin"], "")

    # B-06: sin except vacíos; los errores quedan en el log --------------------------
    def test_backend_sin_except_vacios(self):
        import ast
        vacios = []
        for archivo in (PROJECT_DIR / "backend").glob("*.py"):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
                if isinstance(nodo, ast.ExceptHandler) and nodo.type is None:
                    vacios.append(f"{archivo.name}:{nodo.lineno}")
        self.assertEqual(vacios, [])

    def test_error_del_dashboard_se_registra_y_se_avisa(self):
        import backend_dashboard

        class CursorQueFalla(CursorSimulado):
            def execute(self, sql, *args):
                raise RuntimeError("fallo simulado en la consulta")

        class ConexionQueFalla(ConexionSimulada):
            def cursor(self):
                return CursorQueFalla()

        with patch.object(backend_dashboard, "connect", side_effect=ConexionQueFalla), \
                patch.object(backend_dashboard.logger, "exception") as log:
            r = self.cliente(["Ingresar_dashboard"]).get("/Dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("No fue posible cargar los datos del panel", r.get_data(as_text=True))
        log.assert_called_once_with("error_cargar_dashboard")

    def test_coordenadas_invalidas_del_mapa_se_omiten_y_registran(self):
        import backend_dashboard

        class CursorMapa(CursorSimulado):
            def execute(self, sql, *args):
                self.sql = sql
                return self

            def fetchall(self):
                if "d.direccion IS NOT NULL" in self.sql:
                    return [("4.6,-74.1",), ("abc,def",), ("sin coma",)]
                return []

        class ConexionMapa(ConexionSimulada):
            def cursor(self):
                return CursorMapa()

        with patch.object(backend_dashboard, "connect", side_effect=ConexionMapa), \
                patch.object(backend_dashboard, "render_template", return_value="") as render, \
                patch.object(backend_dashboard.logger, "warning") as aviso, \
                patch.object(backend_dashboard.logger, "exception") as error:
            self.cliente(["Ingresar_dashboard"]).get("/Dashboard/")
        error.assert_not_called()
        self.assertEqual(render.call_args.kwargs["heatdata"], [[4.6, -74.1]])
        aviso.assert_called_once_with("dashboard_coordenadas_invalidas cantidad=%s", 1)

    def test_los_usuarios_no_se_eliminan_solo_se_inactivan(self):
        # El nombre de usuario es la clave foránea de quien registró cada caso: la
        # ruta de borrado ya no existe y la cuenta se inactiva desde "Estado".
        c = self.cliente(["Ingresar_asignar_permisos"])
        r = c.post("/Modulo_permisos_roles/eliminar_usuario", data={"user": "7"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(any("DELETE FROM usuario.usuario " in sql for sql, _ in CONSULTAS))

    # B-04: los eventos de autenticación registran usuario e IP ---------------------
    def test_login_fallido_registra_usuario_e_ip(self):
        import backend_login
        with patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([])), \
                patch.object(backend_login.logger, "warning") as aviso:
            self.app.test_client().post("/", data={"username": "ana.p\nFALSO", "password": "x"},
                                        headers={"X-Forwarded-For": "203.0.113.9"})
        aviso.assert_called_once()
        evento, contexto = aviso.call_args.args
        self.assertTrue(evento.startswith("login_fallido"))
        self.assertEqual(contexto, "usuario=ana.p?FALSO ip=203.0.113.9")

    def test_login_exitoso_y_logout_registran_usuario_e_ip(self):
        import backend_login
        fila = ("ana.p", "hash", "10", 1, 0)
        with patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([fila])), \
                patch.object(backend_login, "check_password_hash", return_value=True), \
                patch.object(backend_login, "cargar_permisos", return_value=[]), \
                patch.object(backend_login.logger, "info") as info:
            c = self.app.test_client()
            c.post("/", data={"username": "ana.p", "password": "x"},
                   headers={"X-Forwarded-For": "198.51.100.4"})
            c.post("/logout", headers={"X-Forwarded-For": "198.51.100.4"})
        eventos = [(c.args[0].split()[0], c.args[1]) for c in info.call_args_list]
        self.assertIn(("login_exitoso", "usuario=ana.p ip=198.51.100.4"), eventos)
        self.assertIn(("logout", "usuario=ana.p ip=198.51.100.4"), eventos)

    def test_error_de_bd_en_login_registra_usuario_e_ip(self):
        import backend_login
        with patch.object(backend_login, "connect", side_effect=RuntimeError("bd caída")), \
                patch.object(backend_login.logger, "exception") as error:
            self.app.test_client().post("/", data={"username": "ana.p", "password": "x"},
                                        headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(error.call_args.args[1], "usuario=ana.p ip=203.0.113.9")

    # M-16: los casos eliminados no suman en el Dashboard ni salen en el Histórico móvil
    def consultas_a_casos(self):
        return [sql for sql, _ in CONSULTAS if "flota.caso d" in sql or "flota.caso AS d" in sql]

    def test_dashboard_excluye_eliminados_en_todas_sus_consultas(self):
        import backend_dashboard
        with patch.object(backend_dashboard, "render_template", return_value=""):
            self.cliente(["Ingresar_dashboard"]).get("/Dashboard/")
        consultas = self.consultas_a_casos()
        self.assertGreaterEqual(len(consultas), 12)
        sin_filtro = [sql.strip()[:80] for sql in consultas if "d.eliminado = 0" not in sql]
        self.assertEqual(sin_filtro, [])

    def test_historico_movil_y_su_excel_excluyen_eliminados(self):
        import backend_historico_movil
        with patch.object(backend_historico_movil, "connect", side_effect=lambda: ConexionSimulada([(0,)])), \
                patch.object(backend_historico_movil, "render_template", return_value=""):
            self.cliente(["Ingresar_danos_vs_reparaciones"]).get("/Historico_movil/?tipo=danos")
            self.cliente(["Ingresar_danos_vs_reparaciones"]).get("/Historico_movil/exportar_excel?tipo=danos")
        consultas = self.consultas_a_casos()
        self.assertTrue(consultas)
        for sql in consultas:
            self.assertIn("d.eliminado = 0", sql)

    def test_detalle_de_caso_eliminado_en_historico_movil_responde_404(self):
        import backend_historico_movil

        class CursorCaso(CursorSimulado):
            description = [("Id",), ("UF",), ("eliminado",)]

            def fetchone(self):
                return (1, "10", 1)

        class ConexionCaso(ConexionSimulada):
            def cursor(self):
                return CursorCaso()

        with patch.object(backend_historico_movil, "connect", side_effect=ConexionCaso):
            r = self.cliente(["Ingresar_danos_vs_reparaciones"]).get("/Historico_movil/detalle/1")
        self.assertEqual(r.status_code, 404)

    # M-17: cada histórico puede abrir todos los adjuntos que lista -----------------
    def abre_adjunto(self, permisos, tipo):
        CONSULTAS.clear()
        r = self.cliente(permisos).get(f"/archivo/1?tipo={tipo}")
        # Con permiso se busca el archivo (404 porque la base simulada no lo tiene);
        # sin permiso se responde 403 antes de consultar.
        return r.status_code != 403 and bool(CONSULTAS)

    def test_usuario_solo_de_historico_de_danos_abre_lo_que_lista(self):
        for tipo in ("operaciones", "mtto", "svial"):
            self.assertTrue(self.abre_adjunto(["Ingresar_historico_danos"], tipo), tipo)
        self.assertFalse(self.abre_adjunto(["Ingresar_historico_danos"], "laboral"))

    def test_usuario_solo_de_historico_movil_abre_lo_que_lista(self):
        for tipo in ("operaciones", "reparaciones"):
            self.assertTrue(self.abre_adjunto(["Ingresar_danos_vs_reparaciones"], tipo), tipo)

    def test_historico_de_danos_solo_lista_documentos_rrll_a_rrll(self):
        import backend_historico_danos
        for permisos, ve_laboral in ((["Ingresar_historico_danos"], False),
                                     (["Ingresar_historico_danos", "Ingresar_modulo__laboral"], True)):
            CONSULTAS.clear()
            with patch.object(backend_historico_danos, "connect",
                              side_effect=lambda: ConexionSimulada([(0,)])), \
                    patch.object(backend_historico_danos, "render_template", return_value=""):
                self.cliente(permisos).get("/Historico_danos/")
            listado = next(sql for sql, _ in CONSULTAS if "archivos_count" in sql)
            self.assertEqual("'Laboral'" in listado, ve_laboral, permisos)

    # B-12: los históricos listan en 1–2 consultas por página ---------------------
    def conexion_con_pagina(self, columnas, fila, filas=30):
        class CursorPagina(CursorSimulado):
            def execute(self, sql, *args):
                CONSULTAS.append((sql, args))
                self.sql = sql
                self.description = [(c,) for c in columnas] if "OFFSET" in sql else [("c",)]
                return self

            def fetchone(self):
                return (filas,)

            def fetchall(self):
                return [fila] * filas if "OFFSET" in self.sql else []

        class ConexionPagina(ConexionSimulada):
            def cursor(self):
                return CursorPagina()

        return ConexionPagina

    def test_historico_de_danos_lista_en_dos_consultas_sin_datos_de_otros_modulos(self):
        import datetime as dt
        import backend_historico_danos
        columnas = ("Id", "Fecha_evento", "Movil", "Fecha_registro", "UF", "Codigo", "Nombre",
                    "estado_caso", "eliminado", "tiene_oper", "tiene_mtto", "tiene_svial",
                    "Fecha_cierre", "archivos_count")
        fila = (1, dt.datetime(2026, 1, 1), "Z32-1001", dt.datetime(2026, 1, 1), "10", "1", "Ana",
                0, 0, 1, 0, 1, None, 2)
        with patch.object(backend_historico_danos, "connect",
                          side_effect=self.conexion_con_pagina(columnas, fila)), \
                patch.object(backend_historico_danos, "render_template", return_value="") as render:
            self.cliente(["Ingresar_historico_danos"]).get("/Historico_danos/")
        self.assertEqual(len(CONSULTAS), 2, [sql.strip()[:60] for sql, _ in CONSULTAS])
        registros = render.call_args.kwargs["registros"]
        self.assertEqual(len(registros), 30)
        for clave in ("oper", "mtto", "svial", "laboral", "laboralm", "correcciones"):
            self.assertNotIn(clave, registros[0], "el listado no debe incluir datos de otros módulos")
        self.assertEqual((registros[0]["tiene_oper"], registros[0]["tiene_mtto"]), (1, 0))

    def test_historico_movil_lista_en_dos_consultas(self):
        import datetime as dt
        import backend_historico_movil
        columnas = ("id", "fecha", "Movil", "UF", "costo", "tipo", "archivos_count")
        fila = (1, dt.datetime(2026, 1, 1), "Z32-1001", "10", 0, "DAÑO", 0)
        with patch.object(backend_historico_movil, "connect",
                          side_effect=self.conexion_con_pagina(columnas, fila)), \
                patch.object(backend_historico_movil, "render_template", return_value=""):
            self.cliente(["Ingresar_danos_vs_reparaciones"]).get("/Historico_movil/")
        self.assertEqual(len(CONSULTAS), 2, [sql.strip()[:60] for sql, _ in CONSULTAS])

    # MVC-8: autorización por defecto con un mapa central ruta → permiso ---------------
    def test_toda_ruta_tiene_regla_en_el_mapa_central(self):
        from autorizacion import regla_para
        sin_regla = sorted(r.endpoint for r in self.app.url_map.iter_rules()
                           if regla_para(r.endpoint) is None)
        self.assertEqual(sin_regla, [], "Rutas sin regla en autorizacion.REGLAS: decláralas")

    def test_el_mapa_no_tiene_reglas_de_rutas_inexistentes(self):
        from autorizacion import REGLAS
        existentes = {r.endpoint for r in self.app.url_map.iter_rules()}
        self.assertEqual(sorted(set(REGLAS) - existentes), [])

    def test_decoradores_y_mapa_central_coinciden(self):
        from autorizacion import regla_para
        distintos = []
        for endpoint, vista in self.app.view_functions.items():
            decorador = set(getattr(vista, "permisos_requeridos", ()))
            regla = regla_para(endpoint)
            if decorador and regla is not None and not decorador <= (regla.todos | regla.alguno):
                distintos.append(f"{endpoint}: decorador {sorted(decorador)} / mapa {regla}")
        self.assertEqual(distintos, [])

    def test_ruta_sin_regla_se_niega_aunque_tenga_todos_los_permisos(self):
        import autorizacion
        todos = sorted({p for r in autorizacion.REGLAS.values() for p in r.todos | r.alguno})
        with patch.dict(autorizacion.REGLAS):
            del autorizacion.REGLAS["Profile.index"]
            r = self.cliente(todos).get("/Profile/")
        self.assertEqual(r.status_code, 403)

    def test_vista_sin_decorador_queda_protegida_por_el_mapa(self):
        from flask import Response
        sin_decorador = lambda **kwargs: Response("contenido del dashboard")  # noqa: E731
        with patch.dict(self.app.view_functions, {"Front_dashboard.index": sin_decorador}):
            r = self.cliente(["Ingresar_captur_danos"]).get("/Dashboard/")
            self.assertEqual(r.status_code, 403)
            r = self.cliente(["Ingresar_dashboard"]).get("/Dashboard/")
            self.assertEqual(r.status_code, 200)

    def test_reglas_compuestas(self):
        from autorizacion import REGLAS
        editar = REGLAS["Modulo_usuario.editar_usuario"]
        self.assertFalse(editar.permite(["Ingresar_crear_usuario"], {}))
        self.assertTrue(editar.permite(["Ingresar_crear_usuario", "Ingresar_asignar_permisos"], {}))
        por_modulo = REGLAS["Modulo_unificado.index"]
        self.assertTrue(por_modulo.permite(["Ingresar_modulo__mtto"], {"modulo": "Mtto"}))
        self.assertFalse(por_modulo.permite(["Ingresar_modulo__mtto"], {"modulo": "Svial"}))
        r = self.cliente(["Ingresar_modulo__mtto"]).get("/NoExiste")
        self.assertEqual(r.status_code, 404)

    # BD-8: cada solicitud de recuperación purga los tokens vencidos, usados o anulados
    def solicitar_recuperacion(self, filas):
        import backend_login
        conexiones, enviados = [], []

        def conectar():
            conexiones.append(ConexionSimulada(list(filas)))
            return conexiones[-1]

        with patch.dict(os.environ, {"APP_BASE_URL": "https://gfd.emasivosas.com.co"}), \
                patch.object(backend_login, "connect", side_effect=conectar), \
                patch.object(backend_login, "enviar_email", side_effect=lambda d, l: enviados.append(l)):
            self.app.test_client().post("/forgot-password", data={"email": "a@b.co"})
        sentencias = [" ".join(sql.split()) for sql, _ in CONSULTAS]
        return sentencias, conexiones[0].commits, enviados

    def test_recuperacion_purga_tokens_y_conserva_el_nuevo(self):
        sentencias, commits, enviados = self.solicitar_recuperacion([(7,)])
        purga = next(i for i, sql in enumerate(sentencias)
                     if sql.startswith("DELETE FROM usuario.restablecimiento_contrasena"))
        anula = next(i for i, sql in enumerate(sentencias) if "SET usado = 1" in sql)
        inserta = next(i for i, sql in enumerate(sentencias)
                       if sql.startswith("INSERT INTO usuario.restablecimiento_contrasena"))
        self.assertLess(anula, purga)     # los anulados también se borran
        self.assertLess(purga, inserta)   # el token nuevo no se purga
        self.assertIn("vence < ? OR usado = 1", sentencias[purga])
        self.assertEqual(commits, 1)
        self.assertEqual(len(enviados), 1)

    def test_recuperacion_con_correo_inexistente_tambien_purga(self):
        sentencias, commits, enviados = self.solicitar_recuperacion([])
        self.assertTrue(any(sql.startswith("DELETE FROM usuario.restablecimiento_contrasena") for sql in sentencias))
        self.assertFalse(any(sql.startswith("INSERT") for sql in sentencias))
        self.assertEqual(commits, 1)
        self.assertEqual(enviados, [])

    # Fechas del caso: el evento no puede quedar después de su registro -------------
    def editar_fecha_evento(self, nueva):
        import datetime as dt
        import backend_unificado
        actual = {"Id": 1, "UF": "10", "Movil": "Z32-7001", "Codigo": "1", "Centro_operaciones": "GAITANA",
                  "Zona_dano": "FRONTAL", "Dano_ocasionado": "VANDALISMO", "Parte_afectada": "ESPEJO",
                  "Fecha_evento": dt.datetime(2026, 10, 5, 5, 0), "Fecha_registro": dt.datetime(2026, 10, 6, 12, 51)}

        class CursorEvento(CursorSimulado):
            description = [(c,) for c in actual]
            sql = ""

            def execute(self, sql, *args):
                self.sql = sql
                return super().execute(sql, *args)

            def fetchone(self):
                if "d.eliminado, d.cerrado" in self.sql:
                    return ("10", 0, 0)
                return tuple(actual.values())

        class ConexionEvento(ConexionSimulada):
            def cursor(self):
                return CursorEvento()

        with patch.object(backend_unificado, "connect", side_effect=ConexionEvento), parchar_catalogos():
            return self.cliente(["Ingresar_modulo__oper", "Corregir_info_oper"]).post(
                "/Operaciones/actualizar_evento/1",
                json={"evento": {"Fecha_evento": nueva}, "motivo_modificacion": "corrección"})

    def test_editar_evento_a_fecha_posterior_al_registro_se_rechaza(self):
        # Caso 449: se editó del 05/10 al 16/10 aunque se había registrado el 06/10.
        r = self.editar_fecha_evento("2026-10-16T05:00")
        self.assertEqual(r.status_code, 400)
        self.assertIn("06/10/2026 12:51", r.get_json()["message"])
        self.assertFalse(any(s.strip().startswith("UPDATE") for s, _ in CONSULTAS))

    def test_editar_evento_con_fecha_mal_formada_responde_400(self):
        r = self.editar_fecha_evento("16/10/2026 05:00")
        self.assertEqual(r.status_code, 400)

    def test_editar_evento_a_fecha_anterior_al_registro_se_guarda(self):
        r = self.editar_fecha_evento("2026-10-05T17:00")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(any(s.strip().startswith("UPDATE flota.caso") for s, _ in CONSULTAS))

    # Carpeta de adjuntos: la del servidor de TI, fija en config.py
    def test_carpeta_de_archivos_es_la_del_servidor_de_ti(self):
        import config
        self.assertEqual(config.MEDIA_DIR, Path("/media/emapp/dano_flota"))
        self.assertEqual(config.UPLOAD_FOLDERS["Operaciones"], Path("/media/emapp/dano_flota/Files/Files_ppal"))

    def test_ruta_guardada_fuera_de_la_carpeta_permitida_se_rechaza(self):
        import config
        intento = "/media/emapp/dano_flota/Files/Files_ppal/../../../secreto.txt"
        self.assertNotIn(config.UPLOAD_FOLDERS["Operaciones"].resolve(), Path(intento).resolve().parents)

    # MVC etapa 1: el Histórico móvil separa controlador, modelo y vista ------------
    def test_historico_movil_cierra_la_conexion_aunque_falle_una_consulta(self):
        import backend_historico_movil
        cerradas = []

        class CursorQueFalla(CursorSimulado):
            def execute(self, sql, *args):
                raise RuntimeError("fallo simulado de SQL Server")

        class ConexionQueFalla(ConexionSimulada):
            def cursor(self):
                return CursorQueFalla()

            def close(self):
                cerradas.append(1)

        for url in ("/Historico_movil/", "/Historico_movil/detalle/1",
                    "/Historico_movil/detalle_reparacion/1", "/Historico_movil/exportar_excel"):
            cerradas.clear()
            with patch.object(backend_historico_movil, "connect", side_effect=ConexionQueFalla):
                r = self.cliente(["Ingresar_danos_vs_reparaciones"]).get(url)
            self.assertEqual(r.status_code, 500, url)
            self.assertEqual(cerradas, [1], f"{url}: la conexión debe cerrarse")

    def test_controlador_del_historico_movil_no_tiene_sql(self):
        import re as _re
        controlador = (PROJECT_DIR / "backend" / "backend_historico_movil.py").read_text(encoding="utf-8")
        self.assertNotIn("execute(", controlador)
        self.assertIsNone(_re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", controlador))
        modelo = (PROJECT_DIR / "backend" / "modelos" / "historico_movil.py").read_text(encoding="utf-8")
        self.assertNotRegex(modelo, r"\bfrom flask\b|\bimport flask\b|\bsession\b|\brequest\b")

    # N-03 / N-04: toda ruta no pública rechaza a un usuario sin permisos -----------
    RUTAS_DE_CUALQUIER_SESION = {
        "Modulo_login.logout", "Profile.index", "Profile.cambiar_password",
        "Tutoriales.index", "Tutoriales.ver_video", "index",
    }
    PUBLICAS = {"Modulo_login.login", "Modulo_login.forgot_password", "Modulo_login.reset_password"}

    def test_toda_ruta_no_publica_exige_permiso(self):
        from flask import url_for
        sin_control = []
        for regla in self.app.url_map.iter_rules():
            ep = regla.endpoint
            if ep == "static" or ep.endswith(".static") or ep in self.PUBLICAS | self.RUTAS_DE_CUALQUIER_SESION:
                continue
            modulos = ["Operaciones", "Mtto", "Svial", "laboral"] if "modulo" in regla.arguments else [None]
            for modulo in modulos:
                valores = {a: (modulo if a == "modulo" else "agregar_oper" if a == "accion" else 1)
                           for a in regla.arguments}
                with self.app.test_request_context():
                    url = url_for(ep, **valores)
                if ep == "Modulo_unificado.descargar_archivo":
                    url += "?tipo=laboral"
                for metodo in regla.methods - {"HEAD", "OPTIONS"}:
                    CONSULTAS.clear()
                    r = self.cliente().open(url, method=metodo, data={"Id_damage_to_fleet": "1"})
                    rechazada = r.status_code in (403, 404, 405)
                    if CONSULTAS or not rechazada:
                        sin_control.append(f"{metodo} {url} -> {r.status_code}")
        self.assertEqual(sin_control, [], "Rutas sin control de permiso")

    def test_adjuntos_de_otros_modulos_visibles_salvo_rrll(self):
        # Regla de negocio: Mantenimiento abre adjuntos de Operaciones y S. Vial.
        for tipo in ("operaciones", "svial"):
            CONSULTAS.clear()
            self.cliente(["Ingresar_modulo__mtto"]).get(f"/archivo/1?tipo={tipo}")
            self.assertTrue(CONSULTAS, f"el permiso de Mantenimiento debe permitir buscar el adjunto {tipo}")

    def test_adjunto_laboral_negado_a_mantenimiento(self):
        # Verificación de TI para N-04: los documentos de RRLL solo los abre RRLL.
        CONSULTAS.clear()
        r = self.cliente(["Ingresar_modulo__mtto", "Ingresar_historico_danos"]).get("/archivo/1?tipo=laboral")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(CONSULTAS, [])

    def test_rrll_abre_adjuntos_de_todos_los_modulos(self):
        for tipo in ("operaciones", "mtto", "svial", "laboral"):
            CONSULTAS.clear()
            self.cliente(["Ingresar_modulo__laboral"]).get(f"/archivo/1?tipo={tipo}")
            self.assertTrue(CONSULTAS, f"RRLL debe poder buscar el adjunto {tipo}")

    def test_adjunto_negado_sin_acceso_a_casos(self):
        r = self.cliente(["Subir_videos"]).get("/archivo/1?tipo=laboral")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(CONSULTAS, [])

    # Cambio 6: CSP estricta en todas las páginas ------------------------------------
    def test_csp_sin_unsafe_inline_en_todas_las_paginas(self):
        for url, permiso in [("/", None), ("/Capturador/", "Ingresar_captur_danos"),
                             ("/Capturador_rep/", "Ingresar_captur_reparaciones"),
                             ("/Videos/Tutoriales", None), ("/Operaciones", "Ingresar_modulo__oper")]:
            r = self.cliente([permiso] if permiso else []).get(url)
            csp = r.headers["Content-Security-Policy"]
            script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src "))
            self.assertNotIn("'unsafe-inline'", script_src, url)
            self.assertIn("'nonce-", script_src, url)
            self.assertIn("script-src-attr 'none'", csp, url)

    def test_plantillas_sin_javascript_en_linea(self):
        for plantilla in (PROJECT_DIR / "frontend").glob("*.html"):
            html = plantilla.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\son[a-z]+\s*=\s*[\"']", html), f"manejador on*= en {plantilla.name}")
            self.assertNotIn("javascript:", html, plantilla.name)
            for etiqueta in re.findall(r"<script\b[^>]*>", html):
                permitido = "src=" in etiqueta or "application/json" in etiqueta or "nonce=" in etiqueta
                self.assertTrue(permitido, f"script en línea sin nonce en {plantilla.name}: {etiqueta}")
            for etiqueta in re.findall(r"<(?:script|link)\b[^>]*https://[^>]*>", html):
                self.assertIn("integrity=", etiqueta, f"CDN sin SRI en {plantilla.name}")

    # Cambio 4: el enlace de recuperación no depende del Host -----------------------
    def test_enlace_recuperacion_ignora_cabecera_host(self):
        import backend_login
        enviados = []
        with patch.dict(os.environ, {"APP_BASE_URL": "https://gfd.emasivosas.com.co"}), \
                patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([(7,)])), \
                patch.object(backend_login, "enviar_email", side_effect=lambda d, l: enviados.append(l)):
            self.app.test_client().post("/forgot-password", data={"email": "a@b.co"},
                                        headers={"Host": "atacante.example"})
        self.assertEqual(len(enviados), 1)
        self.assertTrue(enviados[0].startswith("https://gfd.emasivosas.com.co/reset-password/"))
        self.assertNotIn("atacante", enviados[0])

    def test_sin_app_base_url_no_se_envia_correo(self):
        import backend_login
        enviados = []
        with patch.dict(os.environ, {"APP_BASE_URL": ""}), \
                patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([(7,)])), \
                patch.object(backend_login, "enviar_email", side_effect=lambda d, l: enviados.append(l)):
            r = self.app.test_client().post("/forgot-password", data={"email": "a@b.co"})
        self.assertEqual(enviados, [])
        self.assertEqual(r.status_code, 302)  # mismo mensaje neutro para el usuario

    # M-07: límite de intentos, tokens anulados y en hash, política en todo cambio ---
    def intentar_login(self, username="ana.p", ip="198.51.100.1"):
        import backend_login
        with patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([])):
            return self.app.test_client().post(
                "/", data={"username": username, "password": "x"},
                headers={"X-Forwarded-For": ip})

    def test_login_bloquea_el_sexto_intento_fallido(self):
        for _ in range(5):
            self.assertEqual(self.intentar_login().status_code, 200)
        r = self.intentar_login()
        self.assertEqual(r.status_code, 429)
        self.assertIn("Demasiados intentos", r.get_data(as_text=True))

    def test_login_limite_por_usuario_aunque_cambie_la_ip(self):
        for i in range(5):
            self.intentar_login(ip=f"198.51.100.{i + 10}")
        self.assertEqual(self.intentar_login(ip="198.51.100.99").status_code, 429)

    def test_login_misma_ip_de_empresa_admite_20_errores(self):
        # Varios usuarios salen por la IP de la empresa: el límite por IP es de 20.
        for i in range(20):
            self.assertEqual(self.intentar_login(username=f"usuario{i}").status_code, 200)
        self.assertEqual(self.intentar_login(username="otro").status_code, 429)

    def test_login_exitoso_no_consume_el_limite(self):
        import backend_login
        fila = ("ana.p", "hash", "10", 1, 0)
        with patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([fila])), \
                patch.object(backend_login, "check_password_hash", return_value=True), \
                patch.object(backend_login, "cargar_permisos", return_value=[]):
            for _ in range(8):
                r = self.app.test_client().post("/", data={"username": "ana.p", "password": "x"})
                self.assertEqual(r.status_code, 302)

    def test_recuperacion_guarda_hash_y_anula_enlaces_anteriores(self):
        import hashlib
        import backend_login
        enviados = []
        with patch.dict(os.environ, {"APP_BASE_URL": "https://gfd.emasivosas.com.co"}), \
                patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([(7,)])), \
                patch.object(backend_login, "enviar_email", side_effect=lambda d, l: enviados.append(l)):
            self.app.test_client().post("/forgot-password", data={"email": "a@b.co"})
        token = enviados[0].rsplit("/", 1)[1]
        sentencias = [sql for sql, _ in CONSULTAS]
        anula = next(i for i, sql in enumerate(sentencias) if "SET usado = 1" in sql)
        inserta = next(i for i, sql in enumerate(sentencias) if "INSERT INTO usuario.restablecimiento_contrasena" in sql)
        self.assertLess(anula, inserta)
        guardado = CONSULTAS[inserta][1][0][1]
        self.assertEqual(guardado, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(guardado, token)

    def test_restablecimiento_rechaza_password_debil(self):
        import datetime
        import backend_login
        fila = (7, datetime.datetime.now() + datetime.timedelta(minutes=10), 0, "ana.p")
        with patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([fila])):
            r = self.app.test_client().post("/reset-password/abc", data={"password": "a1"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("al menos 10", r.get_data(as_text=True))
        self.assertFalse(any("UPDATE" in sql for sql, _ in CONSULTAS))
        self.assertNotEqual(CONSULTAS[0][1][0], "abc")  # se busca por el hash, no por el token

    def test_perfil_rechaza_password_debil(self):
        r = self.cliente().post("/Profile/cambiar-password", data={
            "old_password": "Actual2026xx", "new_password": "a1", "confirm_password": "a1"})
        self.assertEqual(r.get_json()["status"], "error")
        self.assertFalse(any("UPDATE" in sql for sql, _ in CONSULTAS))

    # Cambio 5: crear no sobrescribe; editar exige permiso de administración ----------
    DATOS_USUARIO = {"Nombre": "Ana", "IDusuario": "123", "username": "ana.p",
                     "password": "ClaveSegura2026", "UF": "10", "Email": "ana@empresa.co"}

    def test_crear_no_modifica_usuario_existente(self):
        import backend_usuarios
        with patch.object(backend_usuarios, "connect", side_effect=lambda: ConexionSimulada([(1,)])):
            self.cliente(["Ingresar_crear_usuario"]).post("/Modulo_usuario/", data=self.DATOS_USUARIO)
        self.assertFalse(any(re.match(r"\s*(UPDATE|INSERT)", sql) for sql, _ in CONSULTAS), CONSULTAS)

    def test_crear_rechaza_contrasena_debil(self):
        datos = dict(self.DATOS_USUARIO, password="123")
        self.cliente(["Ingresar_crear_usuario"]).post("/Modulo_usuario/", data=datos)
        self.assertEqual(CONSULTAS, [])

    def test_crear_obliga_cambio_de_contrasena(self):
        self.cliente(["Ingresar_crear_usuario"]).post("/Modulo_usuario/", data=self.DATOS_USUARIO)
        insert = [sql for sql, _ in CONSULTAS if "INSERT INTO usuario.usuario" in sql]
        self.assertEqual(len(insert), 1)
        self.assertIn("cambio_contrasena_obligatorio", insert[0])

    def test_editar_exige_permiso_de_administracion(self):
        r = self.cliente(["Ingresar_crear_usuario"]).post(
            "/Modulo_usuario/editar", data={"IDusuario": "123", "password": "ClaveSegura2026"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(CONSULTAS, [])

    def test_editar_no_toca_activo_y_fuerza_cambio_si_asigna_clave(self):
        import backend_usuarios
        with patch.object(backend_usuarios, "connect", side_effect=lambda: ConexionSimulada([("ana.p",)])):
            self.cliente(["Ingresar_crear_usuario", "Ingresar_asignar_permisos"]).post(
                "/Modulo_usuario/editar", data={"IDusuario": "123", "password": "ClaveSegura2026"})
        update = [sql for sql, _ in CONSULTAS if sql.strip().startswith("UPDATE usuario.usuario")]
        self.assertEqual(len(update), 1)
        self.assertNotIn("activo", update[0])
        self.assertIn("cambio_contrasena_obligatorio", update[0])

    # Cambio 2: geocodificador con TLS verificado y timeout --------------------------
    def test_geocodificador_valida_tls_y_usa_timeout(self):
        import backend_capturador
        with patch.object(backend_capturador.requests, "get") as get:
            get.return_value.json.return_value = {"candidates": []}
            self.cliente(["Ingresar_captur_danos"]).get("/Capturador/geocode?q=calle 1")
        _, kwargs = get.call_args
        self.assertNotIn("verify", kwargs)
        self.assertIn("timeout", kwargs)

    # Cambio 3: el módulo no se interpola como valor en el SQL -----------------------
    def test_listado_no_interpola_modulo_en_sql(self):
        for modulo, permiso in [("laboral", "Ingresar_modulo__laboral"), ("Mtto", "Ingresar_modulo__mtto")]:
            CONSULTAS.clear()
            self.cliente([permiso]).get(f"/{modulo}")
            sql = " ".join(s for s, _ in CONSULTAS)
            self.assertNotIn(f"'{modulo}'", sql)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF no está instalado")
class EdicionEventoValidaListasTests(HallazgosAltosTests):
    """N-07: la edición de eventos valida Zona_dano, Dano_ocasionado y Parte_afectada."""

    FILA_ACTUAL = {"Id": 1, "UF": "10", "Movil": "Z32-7001", "Codigo": "1", "Centro_operaciones": "GAITANA",
                   "Zona_dano": "FRONTAL", "Dano_ocasionado": "VANDALISMO", "Parte_afectada": "ESPEJO"}

    def editar(self, cambios):
        import backend_unificado

        class CursorEvento(CursorSimulado):
            description = [(c,) for c in EdicionEventoValidaListasTests.FILA_ACTUAL]
            sql = ""

            def execute(self, sql, *args):
                self.sql = sql
                return super().execute(sql, *args)

            def fetchone(self):
                if "d.eliminado, d.cerrado" in self.sql:
                    return ("10", 0, 0)  # UF, eliminado, cerrado
                return tuple(EdicionEventoValidaListasTests.FILA_ACTUAL.values())

        class ConexionEvento(ConexionSimulada):
            def cursor(self):
                return CursorEvento()

        with patch.object(backend_unificado, "connect", side_effect=ConexionEvento), parchar_catalogos():
            return self.cliente(["Ingresar_modulo__oper", "Corregir_info_oper"]).post(
                "/Operaciones/actualizar_evento/1",
                json={"evento": cambios, "motivo_modificacion": "prueba"})

    def test_rechaza_zona_fuera_de_lista(self):
        r = self.editar({"Zona_dano": "<img src=x onerror=alert(1)>"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(s.strip().startswith("UPDATE") for s, _ in CONSULTAS))

    def test_rechaza_dano_fuera_de_lista(self):
        self.assertEqual(self.editar({"Dano_ocasionado": "OTRO"}).status_code, 400)

    def test_rechaza_parte_afectada_larga(self):
        self.assertEqual(self.editar({"Parte_afectada": "x" * 201}).status_code, 400)

    def test_acepta_valor_de_la_lista(self):
        r = self.editar({"Zona_dano": "TECHO"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
