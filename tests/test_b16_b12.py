"""B-16: los adjuntos antiguos permitidos se muestran en línea sin límite de tamaño
y sin decodificar la imagen en cada vista. B-12: los históricos listan en 1–2
consultas por página."""
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from attachment_security import _tipo_en_linea, inline_type_for_path  # noqa: E402


class AdjuntosEnLineaTests(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp(prefix="dano-flota-b16-"))
        _tipo_en_linea.cache_clear()

    def mp4(self, nombre, tamano_mdat):
        ruta = self.carpeta / nombre
        ftyp = struct.pack(">I", 16) + b"ftyp" + b"isom" + struct.pack(">I", 0x200)
        with ruta.open("wb") as f:
            f.write(ftyp)
            f.write(struct.pack(">I", 8 + tamano_mdat) + b"mdat")
            f.write(b"\0" * tamano_mdat)
        return ruta

    def test_video_antiguo_de_mas_de_5_mb_se_muestra(self):
        ruta = self.mp4("antiguo.mp4", 6 * 1024 * 1024)
        self.assertGreater(ruta.stat().st_size, 5 * 1024 * 1024)
        self.assertEqual(inline_type_for_path(ruta), "video/mp4")

    def test_imagen_grande_se_muestra_sin_decodificarla(self):
        from PIL import Image
        ruta = self.carpeta / "foto.png"
        Image.new("L", (6000, 4000)).save(ruta)  # 24 MP: superaba el límite al validar
        with patch("PIL.ImageFile.ImageFile.load", side_effect=AssertionError("no debe decodificar")):
            self.assertEqual(inline_type_for_path(ruta), "image/png")

    def test_contenido_que_no_coincide_con_la_extension_no_se_muestra(self):
        ruta = self.carpeta / "falsa.jpg"
        ruta.write_bytes(b"<html><script>alert(1)</script></html>")
        self.assertIsNone(inline_type_for_path(ruta))

    def test_pdf_mov_y_avi_siguen_como_descarga(self):
        for nombre in ("doc.pdf", "video.mov", "video.avi"):
            ruta = self.carpeta / nombre
            ruta.write_bytes(b"%PDF-1.4 contenido")
            self.assertIsNone(inline_type_for_path(ruta), nombre)

    def test_la_validacion_se_guarda_y_se_repite_si_el_archivo_cambia(self):
        from PIL import Image
        ruta = self.carpeta / "foto.png"
        Image.new("RGB", (4, 4)).save(ruta)
        with patch("attachment_security.Image.open", wraps=Image.open) as abrir:
            for _ in range(5):
                self.assertEqual(inline_type_for_path(ruta), "image/png")
            self.assertEqual(abrir.call_count, 1)
            ruta.write_bytes(b"ya no es una imagen")
            os.utime(ruta, ns=(1, 1))
            self.assertIsNone(inline_type_for_path(ruta))
            self.assertEqual(abrir.call_count, 2)


if __name__ == "__main__":
    unittest.main()
