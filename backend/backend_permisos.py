from flask import Blueprint, render_template, request, flash, redirect
from config import connect
from backend_security import login_required, requiere_permiso

Modulo_permisos = Blueprint(
    'Modulo_permisos',
    __name__,
    template_folder=r'..\frontend',   # Ajusta según tu carpeta de templates
    static_folder=r'..\Static'        # Ajusta según tu carpeta de CSS/JS
)

@Modulo_permisos.route('/', methods=['GET', 'POST'])
@login_required
@requiere_permiso('Ingresar_permisos')
def crear_permiso():
    conn = connect()
    cursor = conn.cursor()

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        Descripcion = request.form.get('Descripcion')
        if not nombre:
            flash('El nombre del permiso es obligatorio', 'error')
        else:
            # Verificar si ya existe
            cursor.execute("SELECT COUNT(*) FROM Table_permisos WHERE Nombre = ?", nombre)
            existe = cursor.fetchone()[0]
            if existe:
                flash('El permiso ya existe', 'error')
            else:
                # Insertar nuevo rol
                cursor.execute("INSERT INTO Table_permisos (Nombre, Descripcion) VALUES (?, ?)", nombre, Descripcion)
                conn.commit()
                flash('permiso creado correctamente', 'success')
                return redirect('/Modulo_permisos/')

    

    conn.close()
    return render_template('Front_permisos.html')

