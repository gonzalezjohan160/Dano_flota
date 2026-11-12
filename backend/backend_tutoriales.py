from conexiones import conexion_bd
from repositories.sesiones import sesion_bd, abrir_conexion

from contextlib import closing
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from backend_security import login_required, requiere_permiso
from config import BASE_DIR, UPLOAD_FOLDERS, connect
from modelos import tutoriales as modelo_tutoriales


Tutoriales = Blueprint(
    "Tutoriales",
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
)

VIDEO_DIR = UPLOAD_FOLDERS["Tutoriales"]
ALLOWED_EXTENSIONS = {".mp4", ".webm"}
MAX_VIDEO_BYTES = 10 * 1024 * 1024


def _valid_video(upload):
    """Validate extension, browser MIME type and basic container signature."""
    filename = secure_filename(upload.filename or "")
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return False

    expected_mime = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }[extension]

    if upload.mimetype and upload.mimetype not in (
        expected_mime,
        "application/octet-stream",
    ):
        return False

    header = upload.stream.read(32)
    upload.stream.seek(0)

    if extension == ".webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")

    return b"ftyp" in header[4:16]


@Tutoriales.route("/Tutoriales")
@login_required
def index():
    with sesion_bd(connect) as conn:
        with closing(conn.cursor()) as cursor:
            tutoriales = [
                {
                    "id": row[0],
                    "titulo": row[1] or "Tutorial sin título",
                }
                for row in modelo_tutoriales.listar_tutoriales(cursor)
            ]

    return render_template(
        "tutoriales.html",
        tutoriales=tutoriales,
        puede_subir="Subir_videos" in session.get("permisos", []),
        puede_eliminar="Eliminar_videos" in session.get("permisos", []),
        titulo_modulo="Tutoriales",
        tipo_modulo="videos",
    )


@Tutoriales.route("/subir", methods=["POST"])
@login_required
@requiere_permiso("Subir_videos")
def subir():
    # Permite el tamaño del video más el envoltorio multipart de este endpoint.
    request.max_content_length = MAX_VIDEO_BYTES + (64 * 1024)

    if request.content_length and request.content_length > MAX_VIDEO_BYTES + (64 * 1024):
        abort(413)

    upload = request.files.get("video")
    titulo = (request.form.get("titulo") or "").strip()

    if not titulo:
        flash("Escribe el título del tutorial.", "error")
        return redirect(url_for("Tutoriales.index"))

    if len(titulo) > 200:
        flash("El título no puede superar 200 caracteres.", "error")
        return redirect(url_for("Tutoriales.index"))

    if not upload or not upload.filename:
        flash("Selecciona un archivo de video.", "error")
        return redirect(url_for("Tutoriales.index"))

    if not _valid_video(upload):
        flash("El archivo debe ser un video MP4 o WebM válido.", "error")
        return redirect(url_for("Tutoriales.index"))

    upload.stream.seek(0, 2)
    file_size = upload.stream.tell()
    upload.stream.seek(0)

    if file_size == 0 or file_size > MAX_VIDEO_BYTES:
        flash("El video debe pesar como máximo 20 MB.", "error")
        return redirect(url_for("Tutoriales.index"))

    extension = Path(secure_filename(upload.filename)).suffix.lower()
    stored_name = f"{uuid4().hex}{extension}"
    stored_path = VIDEO_DIR / stored_name

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(stored_path)

    conn = None

    try:
        conn = abrir_conexion(connect)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise

    with conexion_bd(conn) as conexion:
        try:
            cursor = conexion.cursor()
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise

        with closing(cursor):
            try:
                modelo_tutoriales.crear_tutorial(
                    cursor, titulo, stored_name, str(stored_path.resolve())
                )
                conexion.commit()
            except Exception:
                stored_path.unlink(missing_ok=True)
                raise

    flash("Video subido correctamente.", "success")
    return redirect(url_for("Tutoriales.index"))


@Tutoriales.route("/eliminar/<int:tutorial_id>", methods=["POST"])
@login_required
@requiere_permiso("Eliminar_videos")
def eliminar(tutorial_id):
    conn = abrir_conexion(connect)
    with conexion_bd(conn):
        try:
            with closing(conn.cursor()) as cursor:
                row = modelo_tutoriales.buscar_archivo_tutorial(cursor, tutorial_id)

                if not row:
                    flash("El tutorial no existe.", "error")
                    return redirect(url_for("Tutoriales.index"))

                filename = secure_filename(row[0] or "")
                file_path = row[1]

                if not filename or not file_path:
                    flash("El archivo del tutorial no es válido.", "error")
                    return redirect(url_for("Tutoriales.index"))

                path = Path(file_path).resolve()

                # Verificación de seguridad:
                # el archivo debe pertenecer exactamente a la carpeta
                # configurada para los tutoriales.
                if (
                    path.parent != VIDEO_DIR.resolve()
                    or path.name != filename
                    or path.suffix.lower() not in ALLOWED_EXTENSIONS
                ):
                    flash("La ubicación del archivo no es válida.", "error")
                    return redirect(url_for("Tutoriales.index"))

                # Primero eliminamos el archivo físico.
                if path.exists():
                    if not path.is_file():
                        flash("El archivo del tutorial no es válido.", "error")
                        return redirect(url_for("Tutoriales.index"))

                    path.unlink()

                # Después eliminamos el registro de SQL Server.
                modelo_tutoriales.eliminar_tutorial(cursor, tutorial_id)

                conn.commit()
        except Exception:
            conn.rollback()
            raise

    flash("Video eliminado correctamente.", "success")
    return redirect(url_for("Tutoriales.index"))


@Tutoriales.route("/video/<int:tutorial_id>")
@login_required
def ver_video(tutorial_id):
    with sesion_bd(connect) as conn:
        with closing(conn.cursor()) as cursor:
            row = modelo_tutoriales.buscar_archivo_tutorial(cursor, tutorial_id)

    if not row:
        abort(404)

    filename = secure_filename(row[0] or "")

    if not row[1]:
        abort(404)

    path = Path(row[1]).resolve()

    if (
        path.parent != VIDEO_DIR.resolve()
        or path.name != filename
        or not path.is_file()
        or path.suffix.lower() not in ALLOWED_EXTENSIONS
    ):
        abort(404)

    mime = (
        "video/webm"
        if path.suffix.lower() == ".webm"
        else "video/mp4"
    )

    return send_file(
        path,
        mimetype=mime,
        conditional=True,
    )

