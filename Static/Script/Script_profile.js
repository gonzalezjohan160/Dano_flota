document.addEventListener('DOMContentLoaded', function() {
    if (window.MOSTRAR_ALERTA_CAMBIO_PASSWORD) {
        alert('Se necesita actualizar la contraseña. Debes actualizarla para continuar.');
    }

    // 1. Cargar datos del JSON (Opcional, según lo que necesites mostrar)
    const datosElemento = document.getElementById('registro-json');
    if (datosElemento) {
        const datosUsuario = JSON.parse(datosElemento.textContent);
        console.log("Cargado perfil de:", datosUsuario.Username);
    }

    // 2. Manejar el formulario
    const form = document.getElementById('changePasswordForm');
    const alerta = document.getElementById('mensaje-alerta');

    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault(); // Detiene el redireccionamiento

            const formData = new FormData(this);

            fetch(URL_CAMBIO_PASS, { // Usamos la variable definida en el HTML
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alerta.style.display = 'block';
                alerta.innerText = data.message;

                if (data.status === 'success') {
                    alerta.style.backgroundColor = '#d4edda';
                    alerta.style.color = '#155724';
                    form.reset();
                } else {
                    alerta.style.backgroundColor = '#f8d7da';
                    alerta.style.color = '#721c24';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alerta.style.display = 'block';
                alerta.innerText = "Error de comunicación con el servidor.";
            });
        });
    }
});
