import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PIL import Image
from werkzeug.datastructures import FileStorage


PROJECT_DIR = Path(__file__).resolve().parents[1]
# Las pruebas escriben su log aparte, no en backend/logs/app.log.
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-logs-"))
# Las pruebas validan la configuración de producción, sin importar el .env local.
os.environ["APP_ENV"] = "prod"
TEST_MEDIA_DIR = tempfile.TemporaryDirectory(prefix="dano-flota-n08-")
os.environ["MEDIA_DIR"] = TEST_MEDIA_DIR.name
os.environ.setdefault("SECRET_KEY", "n08-test-only")
sys.path.insert(0, str(PROJECT_DIR / "backend"))

import attachment_security as security  # noqa: E402
import backend_unificado as unificado  # noqa: E402
import backend_capturador as capturador  # noqa: E402
import backend_reparaciones as reparaciones  # noqa: E402


def make_image(format_name):
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, format=format_name)
    return stream.getvalue()


def file_storage(filename, data):
    return FileStorage(stream=io.BytesIO(data), filename=filename)


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.sql = ""

    def execute(self, sql, params=()):
        self.sql = sql

    def fetchone(self):
        return self.result

    def close(self):
        self.cerrado = True


class FakeConnection:
    def __init__(self, result):
        self.cursor_instance = FakeCursor(result)

    def cursor(self):
        return self.cursor_instance

    def close(self):
        pass


class AttachmentValidationTests(unittest.TestCase):
    def test_valid_raster_images_and_uppercase_extension(self):
        for extension, format_name in (
            ("jpg", "JPEG"), ("png", "PNG"), ("gif", "GIF"), ("webp", "WEBP")
        ):
            with self.subTest(extension=extension):
                self.assertEqual(
                    security.validate_upload(file_storage(f"sample.{extension.upper()}", make_image(format_name))),
                    f".{extension}",
                )

    def test_valid_supported_container_signatures(self):
        mp4 = (
            (20).to_bytes(4, "big") + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isom" +
            (8).to_bytes(4, "big") + b"moov"
        )
        valid = {
            "video.mp4": mp4,
            "video.webm": b"\x1a\x45\xdf\xa3\x42\x82\x84webm",
            "audio.mp3": b"ID3\x04\x00\x00\x00\x00\x00\x00synthetic",
            "audio.ogg": b"OggS\x00synthetic OpusHead",
            "audio.wav": b"RIFF\x04\x00\x00\x00WAVEfmt ",
        }
        for filename, contents in valid.items():
            with self.subTest(filename=filename):
                self.assertEqual(security.validate_upload(file_storage(filename, contents)), Path(filename).suffix)

    def test_active_extensions_and_mismatched_contents_are_rejected(self):
        invalid = (
            ("attack.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"),
            ("attack.html", b"<script>alert(1)</script>"),
            ("fake.jpg", b"<html><script>alert(1)</script></html>"),
            ("truncated.png", b"\x89PNG\r\n\x1a\n"),
            ("empty.gif", b""),
        )
        for filename, contents in invalid:
            with self.subTest(filename=filename), self.assertRaises(security.AttachmentValidationError):
                security.validate_upload(file_storage(filename, contents))

    def test_oversized_upload_is_rejected(self):
        with self.assertRaises(security.AttachmentValidationError):
            security.validate_upload(file_storage("large.jpg", b"x" * (security.MAX_ATTACHMENT_BYTES + 1)))

    def test_upload_count_is_limited_to_five_files(self):
        uploads = [file_storage(f"photo-{index}.jpg", make_image("JPEG")) for index in range(6)]
        with self.assertRaises(security.AttachmentValidationError):
            security.validate_uploads(uploads)

    def test_upload_batch_limits_video_and_other_files_separately(self):
        limit = security.MAX_ATTACHMENT_BYTES
        video_header = b"\x1a\x45\xdf\xa3webm"
        video = file_storage("evidencia.webm", video_header.ljust(limit, b"\0"))
        audio_header = bytes.fromhex(
            "1a45dfa3 87 4282 84 7765626d 18538067 ff 1654ae6b 85 ae83 838102"
        )
        audio = file_storage("grabacion.webm", audio_header.ljust(limit // 4, b"\0"))
        docs = [audio] + [
            file_storage(f"{index}.pdf", b"%PDF-".ljust(limit // 4, b" ")) for index in range(3)
        ]
        self.assertEqual(security.validate_uploads([video, *docs]), [video, *docs])

        cases = (
            ([video, file_storage("segundo.webm", video_header)], "un video"),
            ([file_storage("grande.webm", video_header.ljust(limit + 1, b"\0"))], "5 MB"),
            ([file_storage("grande.pdf", b"%PDF-".ljust(limit, b" ")), docs[0]], "en conjunto"),
            ([*docs, file_storage("otro.pdf", b"%PDF-")], "cuatro archivos"),
        )
        for uploads, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(security.AttachmentValidationError, message):
                security.validate_uploads(uploads)

    def test_path_like_filename_is_sanitized_for_storage(self):
        upload = file_storage("../../evidencia.jpg", make_image("JPEG"))
        security.validate_upload(upload)
        with tempfile.TemporaryDirectory() as folder:
            saved = security.store_upload(upload, folder, upload.filename)
            self.assertEqual(saved.resolve().parent, Path(folder).resolve())
            self.assertNotIn("..", saved.name)
            self.assertLessEqual(len(saved.name), 80)

    def test_invalid_batch_is_rejected_before_storage_directory_is_created(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "case-1"
            request_app = Flask("n08-upload-helper-test")
            with request_app.test_request_context(
                "/Operaciones/agregar_oper", method="POST",
                data={"archivos": [
                    (io.BytesIO(make_image("JPEG")), "valid.jpg"),
                    (io.BytesIO(b"<svg><script>bad</script></svg>"), "bad.svg"),
                ]},
            ):
                cursor = FakeCursor(None)
                with self.assertRaises(security.AttachmentValidationError):
                    unificado.guardar_archivos(cursor, 1, Path(folder))
            self.assertFalse(target.exists())
            self.assertEqual(cursor.sql, "")

    def test_non_numeric_case_identifier_cannot_escape_upload_root(self):
        with tempfile.TemporaryDirectory() as folder:
            with Flask("n08-invalid-case-path").test_request_context("/upload", method="POST"):
                with self.assertRaises(security.AttachmentValidationError):
                    unificado.guardar_archivos(
                        FakeCursor(None), "../../outside", Path(folder)
                    )
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_svg_is_rejected_by_independent_damage_and_repair_upload_routes(self):
        for blueprint, prefix, url, permission, endpoint, module in (
            (capturador.Capturador, "/Capturador", "/Capturador/submit", "Ingresar_captur_danos", capturador, "damage"),
            (reparaciones.Capturador_rep, "/Capturador_rep", "/Capturador_rep/submit", "Ingresar_captur_reparaciones", reparaciones, "repair"),
            (unificado.Modulo_unificado, "", "/Operaciones/agregar_mtto", "Ingresar_modulo__oper", unificado, "unified"),
        ):
            with self.subTest(module=module):
                app = Flask(f"n08-{module}-upload-test")
                app.secret_key = "n08-test-only"
                app.add_url_rule("/login", endpoint="Modulo_login.login", view_func=lambda: "login")
                app.register_blueprint(blueprint, url_prefix=prefix)
                client = app.test_client()
                with client.session_transaction() as session:
                    session["usuario"] = "user"
                    session["permisos"] = [permission]
                with patch.object(endpoint, "connect") as connect:
                    field_name = "archivos" if module == "unified" else "foto_0"
                    response = client.post(url, data={
                        field_name: (io.BytesIO(b"<svg><script>bad</script></svg>"), "bad.svg")
                    }, content_type="multipart/form-data")
                self.assertEqual(response.status_code, 400)
                connect.assert_not_called()


class AttachmentDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="dano-flota-n08-download-")
        cls.app = Flask("n08-download-test")
        cls.app.secret_key = "n08-test-only"
        cls.app.add_url_rule("/login", endpoint="Modulo_login.login", view_func=lambda: "login")
        cls.app.register_blueprint(unificado.Modulo_unificado)
        cls.app.after_request(security.apply_attachment_headers)
        cls.client = cls.app.test_client()
        cls.original_folders = {}
        for key in ("Operaciones", "Mtto", "Svial", "laboral", "Reparaciones"):
            cls.original_folders[key] = unificado.UPLOAD_FOLDERS[key]
            unificado.UPLOAD_FOLDERS[key] = Path(cls.temp.name) / f"Files_{key}"
            unificado.UPLOAD_FOLDERS[key].mkdir()
        cls.upload_root = unificado.UPLOAD_FOLDERS["Operaciones"]

    @classmethod
    def tearDownClass(cls):
        for key, folder in cls.original_folders.items():
            unificado.UPLOAD_FOLDERS[key] = folder
        cls.temp.cleanup()

    def setUp(self):
        self.file_path = self.upload_root / "case-1" / "test.jpg"
        self.file_path.parent.mkdir(exist_ok=True)
        self.file_path.write_bytes(make_image("JPEG"))
        self.db_result = (str(self.file_path), "test.jpg", 10)
        self.connect_patch = patch.object(
            unificado, "connect", side_effect=lambda: FakeConnection(self.db_result)
        )
        self.connect_patch.start()
        self.addCleanup(self.connect_patch.stop)
        with self.client.session_transaction() as session:
            session["usuario"] = "user"
            session["permisos"] = ["Ingresar_modulo__oper"]
            session["UF"] = "10"

    def download(self):
        return self.client.get("/archivo/123?tipo=operaciones")

    def assert_secure_headers(self, response):
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        policy = response.headers.get("Content-Security-Policy", "")
        self.assertIn("sandbox", policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

    def test_valid_jpeg_is_inline_with_correct_mime_and_security_headers(self):
        self.file_path.write_bytes(make_image("JPEG"))
        response = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertIn("inline", response.headers.get("Content-Disposition", ""))
        self.assert_secure_headers(response)
        response.close()

    def test_all_allowlisted_inline_media_keep_their_mime_and_headers(self):
        mp4 = (
            (20).to_bytes(4, "big") + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isom" +
            (8).to_bytes(4, "big") + b"moov"
        )
        samples = {
            "image.png": (make_image("PNG"), "image/png"),
            "image.gif": (make_image("GIF"), "image/gif"),
            "image.webp": (make_image("WEBP"), "image/webp"),
            "video.mp4": (mp4, "video/mp4"),
            "video.webm": (b"\x1a\x45\xdf\xa3\x42\x82\x84webm", "video/webm"),
            "audio.mp3": (b"ID3\x04\x00\x00\x00\x00\x00\x00synthetic", "audio/mpeg"),
            "audio.ogg": (b"OggS\x00synthetic OpusHead", "audio/ogg"),
            "audio.wav": (b"RIFF\x04\x00\x00\x00WAVEfmt ", "audio/wav"),
        }
        for filename, (contents, expected_mime) in samples.items():
            with self.subTest(filename=filename):
                path = self.file_path.with_name(filename)
                path.write_bytes(contents)
                self.db_result = (str(path), filename, 10)
                response = self.download()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, expected_mime)
                self.assertIn("inline", response.headers.get("Content-Disposition", ""))
                self.assert_secure_headers(response)
                response.close()

    def test_download_route_preserves_module_permissions_for_all_attachment_tables(self):
        module_permissions = {
            "operaciones": "Ingresar_modulo__oper",
            "mtto": "Ingresar_modulo__mtto",
            "svial": "Ingresar_modulo__svial",
            "laboral": "Ingresar_modulo__laboral",
            "reparaciones": "Ingresar_captur_reparaciones",
        }
        with self.client.session_transaction() as session:
            session["usuario"] = "user"
            session["permisos"] = list(module_permissions.values())
            session["UF"] = "10"
        for tipo, permission in module_permissions.items():
            with self.subTest(tipo=tipo):
                folder = unificado.UPLOAD_FOLDERS[unificado.ARCHIVOS_POR_TIPO[tipo]["carpeta"]]
                path = folder / "case-1" / "sample.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(make_image("JPEG"))
                self.db_result = (str(path), "sample.jpg", 10)
                response = self.client.get(f"/archivo/123?tipo={tipo}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "image/jpeg")
                self.assert_secure_headers(response)
                response.close()

    def test_download_rejects_attachment_from_another_uf(self):
        self.db_result = (str(self.file_path), "test.jpg", 16)
        response = self.download()
        self.assertEqual(response.status_code, 403)
        response.close()

        with self.client.session_transaction() as session:
            session["UF"] = "invalid"
        self.db_result = (str(self.file_path), "test.jpg", 10)
        response = self.download()
        self.assertEqual(response.status_code, 403)
        response.close()

    def test_transversal_user_can_access_only_the_two_authorized_ufs(self):
        with self.client.session_transaction() as session:
            session["UF"] = "TRANSVERSAL"
        self.db_result = (str(self.file_path), "test.jpg", 16)
        response = self.download()
        self.assertEqual(response.status_code, 200)
        response.close()

        self.db_result = (str(self.file_path), "test.jpg", 20)
        response = self.download()
        self.assertEqual(response.status_code, 403)
        response.close()

    def test_legacy_active_and_unknown_files_are_attachment_octet_stream(self):
        for filename, contents in (
            ("old.svg", b"<svg><script>alert(1)</script></svg>"),
            ("old.html", b"<script>alert(1)</script>"),
            ("unknown.bin", b"unknown"),
            ("fake.jpg", b"<html>not a jpeg</html>"),
        ):
            with self.subTest(filename=filename):
                path = self.file_path.with_suffix(Path(filename).suffix)
                path.write_bytes(contents)
                self.db_result = (str(path), filename, 10)
                response = self.download()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "application/octet-stream")
                self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
                self.assert_secure_headers(response)
                response.close()

    def test_authentication_and_permission_are_preserved(self):
        with self.client.session_transaction() as session:
            session.clear()
        response = self.download()
        self.assertEqual(response.status_code, 302)
        response.close()
        with self.client.session_transaction() as session:
            session["usuario"] = "user"
            session["permisos"] = []
        response = self.download()
        self.assertEqual(response.status_code, 403)
        self.assert_secure_headers(response)
        response.close()

    def test_missing_attachment_response_keeps_security_headers(self):
        self.db_result = None
        response = self.download()
        self.assertEqual(response.status_code, 404)
        self.assert_secure_headers(response)
        response.close()

if __name__ == "__main__":
    unittest.main()
