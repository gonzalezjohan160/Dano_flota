"""Reglas de arquitectura de todo el proyecto (hallazgos de la sección 8 de la auditoría).

Pruebas estáticas: leen el código, no ejecutan la aplicación ni usan base de datos.
Si una falla, el cambio reintroduce un problema que ya se había corregido.
"""
import ast
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
LIMITE_LINEAS = 350
SQL = re.compile(r"\b(SELECT\s|INSERT\s+INTO|UPDATE\s+[\w\[\].]+\s+SET|DELETE\s+FROM)")

# Herramientas de esquema (aplican migraciones e inspeccionan metadatos) y la propia
# función connect: ejecutar SQL y manejar la conexión es justo su trabajo.
INFRAESTRUCTURA_BD = {"config.py", "manage_db.py", "schema_migrations.py", "conexiones.py"}
CONTROLADORES = [p for p in sorted(BACKEND.glob("*.py")) + sorted((BACKEND / "unificado").glob("*.py"))
                 if p.name not in INFRAESTRUCTURA_BD]
SIN_FLASK = sorted((BACKEND / "modelos").glob("*.py")) + sorted((BACKEND / "servicios").glob("*.py")) \
    + sorted((BACKEND / "vistas").glob("*.py"))
PLANTILLAS = sorted((RAIZ / "frontend").rglob("*.html"))
SCRIPTS = sorted((RAIZ / "Static" / "Script").rglob("*.js"))
# Trozos de HTML que el propio JS arma escapando cada dato, o constantes internas.
HTML_YA_ESCAPADO = {
    "observacionesHTML", "correccionesHTML", "celdaFechaLaboral", "celdaAdjuntos", "celdaAcciones",
    "htmlGeneral", "htmlOper", "htmlMtto", "htmlSvial", "htmlLaboral", "estadoCaso.clase", "campo.label",
    "min", "sec",
}
FUNCIONES_QUE_ESCAPAN = ("escaparHtml(", "iconoCheck(", "opcionesSelect(", "construirAvisosPendienteLaboral(")


def leer(ruta):
    return ruta.read_text(encoding="utf-8")


def llamada(nodo, *nombres):
    return isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", getattr(nodo.func, "id", None)) in nombres


class CapasTests(unittest.TestCase):
    def test_el_sql_solo_vive_en_los_modelos(self):
        for ruta in CONTROLADORES + SIN_FLASK:
            if ruta.parent.name == "modelos":
                continue
            arbol = ast.parse(leer(ruta))
            with self.subTest(archivo=ruta.name):
                textos = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                self.assertEqual([t[:50] for t in textos if SQL.search(t)], [])
                self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr == "execute" for n in ast.walk(arbol)))

    def test_modelos_servicios_y_vistas_no_dependen_de_flask(self):
        for ruta in SIN_FLASK:
            arbol = ast.parse(leer(ruta))
            importados = {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
            importados |= {n.module.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module}
            nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
            with self.subTest(archivo=f"{ruta.parent.name}/{ruta.name}"):
                self.assertFalse(importados & {"flask", "werkzeug", "config"})
                self.assertFalse(nombres & {"request", "session", "connect"})

    def test_conexiones_y_cursores_se_cierran_con_closing(self):
        for ruta in CONTROLADORES:
            arbol = ast.parse(leer(ruta))
            protegidos, nombres_protegidos = set(), set()
            for nodo in ast.walk(arbol):
                if llamada(nodo, "closing", "conexion_bd") and nodo.args:
                    protegidos.add(id(nodo.args[0]))
                    if isinstance(nodo.args[0], ast.Name):
                        nombres_protegidos.add(nodo.args[0].id)
            asignados = {id(n.value): n.targets[0].id for n in ast.walk(arbol)
                         if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
            for nodo in ast.walk(arbol):
                if llamada(nodo, "connect", "cursor") and id(nodo) not in protegidos:
                    with self.subTest(archivo=ruta.name, linea=nodo.lineno):
                        self.assertIn(asignados.get(id(nodo)), nombres_protegidos)

    def test_ningun_archivo_supera_el_limite_de_lineas(self):
        archivos = sorted(BACKEND.rglob("*.py")) + SCRIPTS + PLANTILLAS
        for ruta in archivos:
            if "__pycache__" in ruta.parts:
                continue
            with self.subTest(archivo=str(ruta.relative_to(RAIZ))):
                self.assertLessEqual(len(leer(ruta).splitlines()), LIMITE_LINEAS)


class VistasTests(unittest.TestCase):
    def test_plantillas_sin_estilos_ni_scripts_en_linea(self):
        for ruta in PLANTILLAS:
            texto = re.sub(r"<!--.*?-->|\{#.*?#\}", "", leer(ruta), flags=re.S)
            with self.subTest(plantilla=ruta.name):
                self.assertNotIn("<style", texto)
                self.assertIsNone(re.search(r"\son[a-z]+\s*=", texto))
                for etiqueta in re.findall(r"<script\b[^>]*>", texto):
                    # El único permitido es el csrfFetch de la base, con nonce de la CSP.
                    if ruta.name == "Interfaz.html" and "csp_nonce" in etiqueta:
                        continue
                    self.assertRegex(etiqueta, r'\ssrc=|type="application/json"')
                # Solo display queda en línea: el JavaScript lo cambia con element.style.display.
                for estilo in re.findall(r'\sstyle="([^"]*)"', texto, flags=re.S):
                    propiedades = {d.split(":")[0].strip() for d in estilo.split(";") if d.strip()}
                    self.assertEqual(propiedades - {"display"}, set(), estilo)

    def test_los_archivos_estaticos_enlazados_existen(self):
        estaticos = RAIZ / "Static"
        for ruta in PLANTILLAS:
            for archivo in re.findall(r"filename='([^']+)'", leer(ruta)):
                with self.subTest(plantilla=ruta.name, archivo=archivo):
                    self.assertTrue((estaticos / archivo).is_file())

    def test_html_generado_por_javascript_escapa_los_datos(self):
        for ruta in SCRIPTS:
            texto = leer(ruta)
            for plantilla in re.finditer(r"`([^`]*)`", texto):
                if "<" not in plantilla.group(1):
                    continue
                for expresion in re.findall(r"\$\{([^}]*)\}", plantilla.group(1)):
                    expresion = expresion.strip()
                    linea = texto[:plantilla.start()].count("\n") + 1
                    with self.subTest(archivo=ruta.name, linea=linea, expresion=expresion[:40]):
                        seguro = expresion in HTML_YA_ESCAPADO or any(f in expresion for f in FUNCIONES_QUE_ESCAPAN) \
                            or re.fullmatch(r"[\w.]+ \? \"[\w-]*\" : \"[\w-]*\"|.*\? \"selected\" : \"\"", expresion) is not None \
                            or expresion.startswith(("centroActual ?", "hayPendienteLaboral"))
                        self.assertTrue(seguro, "use escaparHtml() para los datos dentro de HTML")

    def test_las_funciones_que_arman_html_escapan_sus_datos(self):
        utilidades = leer(RAIZ / "Static" / "Script" / "Modulo_unificado" / "edicion_evento.js")
        opciones = utilidades[utilidades.index("function opcionesSelect("):][:400]
        self.assertIn("escaparHtml(valor)", opciones)


if __name__ == "__main__":
    unittest.main()
