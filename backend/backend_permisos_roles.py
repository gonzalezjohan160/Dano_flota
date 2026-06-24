from flask import Blueprint, render_template, request, flash, redirect
from config import connect
from backend_security import login_required, requiere_permiso

Modulo_permisos_roles = Blueprint(
    'Modulo_permisos_roles',
    __name__,
    template_folder=r'..\frontend',
    static_folder=r'..\Static'
)

@Modulo_permisos_roles.route('/', methods=['GET', 'POST'])
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def asignar_permisos():
    conn = connect()
    cursor = conn.cursor()

    # Traer usuarios y permisos existentes
    cursor.execute("SELECT ConsID, Nombre FROM Table_usuarios")
    users = cursor.fetchall()

    cursor.execute("SELECT PermisoID, Nombre FROM Table_permisos")
    permisos = cursor.fetchall()

    if request.method == 'POST':
        user_id = request.form['user']
        permisos_ids = request.form.getlist('permisos')

        # Primero eliminar permisos anteriores del rol
        cursor.execute("DELETE FROM Table_usuarios_permisos WHERE UserID = ?", user_id)

        # Insertar nuevos permisos
        for pid in permisos_ids:
            cursor.execute("INSERT INTO Table_usuarios_permisos (UserID, PermisoID) VALUES (?, ?)", user_id, pid)
        conn.commit()
        flash('Permisos asignados correctamente', 'success')
        return redirect('/Modulo_permisos_roles/')

    conn.close()
    return render_template('Front_permisos_roles.html', users=users, permisos=permisos)

