(() => {
    // Tras una operación exitosa se recarga la página, como hacía el script en línea anterior.
    if (document.querySelector('.flash-messages .flash-success')) {
        setTimeout(() => window.location.reload(), 2000);
    }

    const selectorUsuarioPermisos = document.getElementById('usuario_permisos');
    const selectorEstadoUsuario = document.getElementById('estado_usuario');
    const casillasPermisos = Array.from(document.querySelectorAll("input[name='permisos']"));
    const usuariosCambioPassword = Array.from(document.querySelectorAll('.usuario-cambio-password'));
    const seleccionarTodosCambioPassword = document.getElementById('seleccionar_todos_cambio_password');
    const contenedorSelectorUsuarios = document.getElementById('selector-usuarios');
    const botonSelectorUsuarios = document.getElementById('selector_usuarios_toggle');
    const textoSelectorUsuarios = document.getElementById('texto-selector-usuarios');

    botonSelectorUsuarios.addEventListener('click', () => {
        const abierto = contenedorSelectorUsuarios.classList.toggle('abierto');
        botonSelectorUsuarios.setAttribute('aria-expanded', abierto);
    });

    document.addEventListener('click', evento => {
        if (!contenedorSelectorUsuarios.contains(evento.target)) {
            contenedorSelectorUsuarios.classList.remove('abierto');
            botonSelectorUsuarios.setAttribute('aria-expanded', 'false');
        }
    });

    function actualizarTextoSelectorUsuarios() {
        const seleccionados = usuariosCambioPassword.filter(usuario => usuario.checked);
        if (seleccionados.length === 0) {
            textoSelectorUsuarios.textContent = 'Seleccione uno o varios usuarios';
        } else if (seleccionados.length === 1) {
            textoSelectorUsuarios.textContent = seleccionados[0].dataset.nombre;
        } else {
            textoSelectorUsuarios.textContent = `${seleccionados.length} usuarios seleccionados`;
        }
    }

    async function cargarPermisosUsuarioSeleccionado() {
        const seleccionados = usuariosCambioPassword.filter(usuario => usuario.checked);
        casillasPermisos.forEach(casilla => {
            casilla.checked = false;
        });

        selectorUsuarioPermisos.value = seleccionados.length === 1 ? seleccionados[0].value : '';
        if (seleccionados.length !== 1) return;

        const usuarioSeleccionado = seleccionados[0];
        const userId = usuarioSeleccionado.value;
        selectorEstadoUsuario.value = usuarioSeleccionado.dataset.activo;

        try {
            const respuesta = await fetch(`/Modulo_permisos_roles/permisos_usuario/${encodeURIComponent(userId)}`);
            if (!respuesta.ok) throw new Error('No fue posible consultar los permisos.');

            const datos = await respuesta.json();
            // Si el usuario cambió mientras llegaba la respuesta, se descarta.
            if (selectorUsuarioPermisos.value !== userId) return;

            const permisosAsignados = new Set((datos.permisos || []).map(String));
            casillasPermisos.forEach(casilla => {
                casilla.checked = permisosAsignados.has(casilla.value);
            });
        } catch (error) {
            console.error(error);
            alert('No fue posible cargar los permisos del usuario seleccionado.');
        }
    }

    usuariosCambioPassword.forEach(casilla => {
        casilla.addEventListener('change', () => {
            const seleccionados = usuariosCambioPassword.filter(usuario => usuario.checked).length;
            seleccionarTodosCambioPassword.checked = seleccionados === usuariosCambioPassword.length;
            seleccionarTodosCambioPassword.indeterminate = seleccionados > 0 && seleccionados < usuariosCambioPassword.length;
            actualizarTextoSelectorUsuarios();
            cargarPermisosUsuarioSeleccionado();
        });
    });

    seleccionarTodosCambioPassword.addEventListener('change', () => {
        usuariosCambioPassword.forEach(usuario => {
            usuario.checked = seleccionarTodosCambioPassword.checked;
        });
        actualizarTextoSelectorUsuarios();
        cargarPermisosUsuarioSeleccionado();
    });

    function validarUsuarioUnico() {
        const seleccionados = usuariosCambioPassword.filter(usuario => usuario.checked).length;
        if (seleccionados !== 1) {
            alert('Seleccione exactamente un usuario para asignar permisos.');
            return false;
        }
        return true;
    }

    function validarSeleccionCambioPassword() {
        if (!usuariosCambioPassword.some(usuario => usuario.checked)) {
            alert('Debe seleccionar al menos un usuario.');
            return false;
        }
        return true;
    }

    function confirmarEliminacionUsuario() {
        if (!validarUsuarioUnico()) {
            return false;
        }
        return confirm('¿Está seguro de que desea eliminar este usuario? Esta acción eliminará también todos los permisos asociados y no se puede deshacer.');
    }

    // Reemplazan los onclick="return ..." que la CSP ya no permite.
    const validaciones = {
        'btn-asignar-permisos': validarUsuarioUnico,
        'btn-forzar-cambio-password': validarSeleccionCambioPassword,
        'btn-eliminar-usuario': confirmarEliminacionUsuario,
    };
    Object.entries(validaciones).forEach(([id, validar]) => {
        const boton = document.getElementById(id);
        if (!boton) return;
        boton.addEventListener('click', evento => {
            if (!validar()) evento.preventDefault();
        });
    });
})();
