"""N-10: todo paquete externo que importa el backend está fijado en requirements.txt."""
import ast
import re
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"

# Nombre con el que se importa -> nombre del paquete en requirements.txt
PAQUETE_DE_MODULO = {
    "PIL": "pillow",
    "dotenv": "python-dotenv",
    "flask_wtf": "flask-wtf",
    "flask_limiter": "flask-limiter",
}


def normalizar(nombre):
    return re.sub(r"[-_.]+", "-", nombre).lower()


class RequirementsTests(unittest.TestCase):
    def test_imports_externos_estan_en_requirements(self):
        # Módulos propios: archivos .py del backend y sus paquetes (modelos/, vistas/...).
        locales = {p.stem for p in BACKEND_DIR.glob("*.py")}
        locales |= {p.parent.name for p in BACKEND_DIR.glob("*/__init__.py")}
        modulos = set()
        for archivo in BACKEND_DIR.rglob("*.py"):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
                if isinstance(nodo, ast.Import):
                    modulos.update(a.name.split(".")[0] for a in nodo.names)
                elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
                    modulos.add(nodo.module.split(".")[0])
        externos = modulos - locales - set(sys.stdlib_module_names) - {"__future__"}

        fijados = {}
        for linea in (PROJECT_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                nombre, _, version = linea.partition("==")
                fijados[normalizar(nombre)] = version

        faltantes = sorted(m for m in externos
                           if normalizar(PAQUETE_DE_MODULO.get(m, m)) not in fijados)
        self.assertEqual(faltantes, [], "Paquetes importados que no están en requirements.txt")
        sin_version = sorted(n for n, v in fijados.items() if not v)
        self.assertEqual(sin_version, [], "Paquetes sin versión fija (==)")

    def test_dependencias_indirectas_tambien_estan_fijadas(self):
        # B-11: Flask-WTF instala WTForms; todo lo que se instala debe estar fijado
        # para que requirements.txt coincida con pip freeze.
        from importlib import metadata
        from packaging.requirements import Requirement

        fijados = {}
        for linea in (PROJECT_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines():
            if linea.strip() and not linea.startswith("#"):
                nombre, _, version = linea.strip().partition("==")
                fijados[normalizar(nombre)] = version

        sin_fijar = set()
        for nombre in fijados:
            try:
                requeridos = metadata.requires(nombre) or []
            except metadata.PackageNotFoundError:
                continue  # el entorno de pruebas no tiene instalado este paquete
            for texto in requeridos:
                req = Requirement(texto)
                if req.marker and not req.marker.evaluate({"extra": ""}):
                    continue
                if normalizar(req.name) not in fijados:
                    sin_fijar.add(f"{req.name} (lo requiere {nombre})")
        self.assertEqual(sorted(sin_fijar), [], "Dependencias indirectas sin fijar")


if __name__ == "__main__":
    unittest.main()
