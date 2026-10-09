"""Validación y almacenamiento seguro de archivos adjuntos."""

import shutil
import warnings
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename


MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENTS_PER_REQUEST = 5
MAX_IMAGE_PIXELS = 20_000_000
ATTACHMENT_CSP = (
    "default-src 'none'; script-src 'none'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; sandbox"
)

INLINE_TYPES = {
    ".jpg": ("image/jpeg", "jpeg"),
    ".jpeg": ("image/jpeg", "jpeg"),
    ".png": ("image/png", "png"),
    ".gif": ("image/gif", "gif"),
    ".webp": ("image/webp", "webp"),
    ".mp4": ("video/mp4", "mp4"),
    ".webm": ("video/webm", "webm"),
    ".mp3": ("audio/mpeg", "mp3"),
    ".ogg": ("audio/ogg", "ogg"),
    ".wav": ("audio/wav", "wav"),
}

# Conserva los formatos que ya admitían los capturadores. Estos formatos
# adicionales solo se entregan como descarga, nunca como contenido en línea.
DOWNLOAD_ONLY_TYPES = {".pdf", ".avi", ".mov", ".opus"}
ALLOWED_UPLOAD_EXTENSIONS = set(INLINE_TYPES) | DOWNLOAD_ONLY_TYPES


class AttachmentValidationError(ValueError):
    """Error controlado que puede mostrarse al usuario."""


def _stream_size(upload):
    stream = upload.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    return size


def _read_header(upload):
    upload.stream.seek(0)
    header = upload.stream.read(65536)
    upload.stream.seek(0)
    return header


def _valid_iso_bmff(upload, allowed_brands):
    stream = upload.stream
    stream.seek(0, 2)
    total_size = stream.tell()
    stream.seek(0)
    position = 0
    has_ftyp = False
    has_media_box = False
    valid_brand = False
    while position + 8 <= total_size:
        stream.seek(position)
        box_header = stream.read(16)
        if len(box_header) < 8:
            return False
        box_size = int.from_bytes(box_header[:4], "big")
        box_type = box_header[4:8]
        header_size = 8
        if box_size == 1:
            if len(box_header) < 16:
                return False
            box_size = int.from_bytes(box_header[8:16], "big")
            header_size = 16
        elif box_size == 0:
            box_size = total_size - position
        if box_size < header_size or position + box_size > total_size:
            return False
        if box_type == b"ftyp":
            if box_size < header_size + 8:
                return False
            has_ftyp = True
            stream.seek(position + header_size)
            brands = stream.read(box_size - header_size)
            valid_brand = any(
                brands[offset:offset + 4] in allowed_brands
                for offset in range(0, len(brands), 4)
            )
        if box_type in (b"moov", b"mdat"):
            has_media_box = True
        position += box_size
    stream.seek(0)
    return position == total_size and has_ftyp and has_media_box and valid_brand


def _valid_image(upload, extension):
    expected = {
        ".jpg": {"JPEG"}, ".jpeg": {"JPEG"}, ".png": {"PNG"},
        ".gif": {"GIF"}, ".webp": {"WEBP"},
    }[extension]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.stream.seek(0)
            with Image.open(upload.stream) as image:
                if image.format not in expected:
                    return False
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    return False
                image.verify()
            upload.stream.seek(0)
            with Image.open(upload.stream) as image:
                image.load()
        return True
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        return False
    finally:
        upload.stream.seek(0)


def _valid_signature(upload, extension):
    header = _read_header(upload)
    if extension in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return _valid_image(upload, extension)
    if extension == ".mp4":
        mp4_brands = {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"mp4v", b"M4V "}
        return (
            len(header) >= 12 and header[4:8] == b"ftyp"
            and _valid_iso_bmff(upload, mp4_brands)
        )
    if extension == ".webm":
        return header.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in header[:4096]
    if extension == ".mp3":
        return header.startswith(b"ID3") or (
            len(header) > 1 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        )
    if extension == ".ogg":
        return header.startswith(b"OggS") and (b"OpusHead" in header or b"vorbis" in header)
    if extension == ".opus":
        return header.startswith(b"OggS") and b"OpusHead" in header
    if extension == ".wav":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    if extension == ".avi":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"AVI "
    if extension == ".mov":
        return (
            len(header) >= 12
            and header[4:8] == b"ftyp"
            and _valid_iso_bmff(upload, {b"qt  "})
        )
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    return False


def validate_upload(upload, filename=None, max_bytes=MAX_ATTACHMENT_BYTES):
    filename = upload.filename if filename is None else filename
    safe_name = secure_filename(filename or "")
    extension = Path(safe_name).suffix.lower()
    if not safe_name or not extension:
        raise AttachmentValidationError("Cada archivo debe tener un nombre y una extensión válidos.")
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise AttachmentValidationError("El formato de archivo no está permitido.")

    size = _stream_size(upload)
    if size <= 0:
        raise AttachmentValidationError("No se permiten archivos vacíos.")
    if size > max_bytes:
        raise AttachmentValidationError("Cada archivo puede pesar como máximo 5 MB.")
    if not _valid_signature(upload, extension):
        raise AttachmentValidationError("El contenido del archivo no coincide con su formato.")

    return extension


def validate_uploads(uploads, max_files=MAX_ATTACHMENTS_PER_REQUEST):
    present = [upload for upload in uploads if upload and upload.filename]
    if len(present) > max_files:
        raise AttachmentValidationError(f"Máximo {max_files} archivos permitidos.")
    for upload in present:
        validate_upload(upload)
    return present


def store_upload(upload, directory, filename):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(filename or "")
    if not safe_name:
        raise AttachmentValidationError("No fue posible asignar un nombre seguro al archivo.")

    suffix = Path(safe_name).suffix
    stem = Path(safe_name).stem
    # Las tablas de captura guardan FileName en varchar(80).
    stem = stem[:max(1, 80 - len(suffix) - 33)]
    target = (directory / f"{stem}_{uuid4().hex}{suffix}").resolve()
    if target.parent != directory:
        raise AttachmentValidationError("La ruta del archivo no es válida.")

    try:
        upload.stream.seek(0)
        with target.open("xb") as destination:
            shutil.copyfileobj(upload.stream, destination, length=1024 * 1024)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        upload.stream.seek(0)
    return target


def inline_type_for_path(path):
    """Devuelve MIME seguro solo si extensión y contenido real son permitidos."""
    path = Path(path)
    extension = path.suffix.lower()
    allowed = INLINE_TYPES.get(extension)
    if not allowed:
        return None
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > MAX_ATTACHMENT_BYTES:
            return None
        with path.open("rb") as stream:
            class UploadView:
                filename = path.name

                def __init__(self, file_stream):
                    self.stream = file_stream

            if not _valid_signature(UploadView(stream), extension):
                return None
    except (OSError, ValueError):
        return None
    return allowed[0]


def apply_attachment_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = ATTACHMENT_CSP
    response.headers["X-Frame-Options"] = "DENY"
    return response
