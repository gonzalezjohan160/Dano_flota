from flask import Blueprint, render_template, request, flash, redirect
from config import connect
from werkzeug.security import generate_password_hash
from backend_security import login_required, requiere_permiso
from config import BASE_DIR

Modulo_usuario = Blueprint(
    'Modulo_usuario',
    __name__,
    template_folder=str(BASE_DIR/"frontend"),  
    static_folder=str(BASE_DIR/"Static")       
)

@Modulo_usuario.route('/', methods=['GET', 'POST'])
@login_required
@requiere_permiso('Ingresar_crear_usuario')
def crear_usuario():
    conn = connect()
    cursor = conn.cursor()

    if request.method == 'POST':
        # 1. Captura de datos del formulario
        Nombre = request.form.get('Nombre')
        IDusuario = request.form.get('IDusuario') # Viene del input name="IDusuario"
        username = request.form.get('username')   # Viene del input name="username"
        password = request.form.get('password')
        Correo = request.form.get('Email')        # Viene del input name="Email"
        UF = request.form.get('UF')
        Activo = 1  # Usamos entero si en SQL es Bit o Int

        if not username or not IDusuario:
            flash('Nombre de usuario e Identificación son obligatorios', 'error')
        else:
            # 2. VALIDACIÓN: ¿El Username ya lo tiene OTRA persona?
            # Buscamos si el username existe y traemos su IDusuario para comparar
            cursor.execute("SELECT IDusuario FROM Table_usuarios WHERE Username = ?", (username,))
            user_check = cursor.fetchone()

            # Si existe el username pero el IDusuario es diferente al que estamos escribiendo: BLOQUEO
            if user_check and str(user_check[0]) != str(IDusuario):
                flash(f'El nombre de usuario "{username}" ya está asignado a otra identificación.', 'error')
            
            else:
                # 3. VALIDACIÓN: ¿Existe el IDusuario para decidir entre UPDATE o INSERT?
                cursor.execute("SELECT COUNT(*) FROM Table_usuarios WHERE IDusuario = ?", (IDusuario,))
                existe_id = cursor.fetchone()[0]

                if existe_id > 0:
                    # --- OPERACIÓN: UPDATE (Modificar registro existente) ---
                    if password: # Si el usuario escribió algo en el campo password
                        password_hash = generate_password_hash(password)
                        query = """
                            UPDATE Table_usuarios 
                            SET Username = ?, PasswordHash = ?, Nombre = ?, Email = ?, Activo = ?, UF = ?
                            WHERE IDusuario = ?
                        """
                        cursor.execute(query, (username, password_hash, Nombre, Correo, Activo, UF, IDusuario))
                    else:
                        # Update sin tocar la contraseña actual
                        query = """
                            UPDATE Table_usuarios 
                            SET Username = ?, Nombre = ?, Email = ?, Activo = ?, UF = ?
                            WHERE IDusuario = ?
                        """
                        cursor.execute(query, (username, Nombre, Correo, Activo, UF, IDusuario))
                    
                    conn.commit()
                    flash('Usuario actualizado correctamente (El ID ya existía)', 'success')
                
                else:
                    # --- OPERACIÓN: INSERT (Crear nuevo) ---
                    password_hash = generate_password_hash(password)
                    cursor.execute(
                        """INSERT INTO Table_usuarios (Username, PasswordHash, Nombre, Email, Activo, IDusuario, UF) 
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (username, password_hash, Nombre, Correo, Activo, IDusuario, UF)
                    )
                    conn.commit()
                    flash('Usuario creado exitosamente', 'success')

                return redirect('/Modulo_usuario/')

    conn.close()
    return render_template('Front_usuarios.html')

