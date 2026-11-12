// Capturador reparaciones — adjuntos, compresión de imágenes y envío del formulario.
// Antes formaba parte de Script_captur_rep.js; se carga en orden desde frontend/Capturador_reparaciones.html.

        /* =========================================================
        CAPTURADOR DE ADJUNTOS - SE ACUMULAN Y SE PUEDEN BORRAR
        ========================================================= */
        window.adjuntosSeleccionados = [];  // Almacenará TODOS los archivos seleccionados
        const inputAdjuntos = document.getElementById("evidencia");
        const listaAdjuntos = document.getElementById("lista_adjuntos");

        // Cuando el usuario selecciona archivos
        inputAdjuntos.addEventListener("change", () => {
            const nuevosArchivos = Array.from(inputAdjuntos.files);

            // Agregar SIN reemplazar
            nuevosArchivos.forEach(file => adjuntosSeleccionados.push(file));

            // Limpiar el input para evitar duplicados visuales
            inputAdjuntos.value = "";

            actualizarListaAdjuntos();
        });

        // Redibuja la lista
        function actualizarListaAdjuntos() {
            listaAdjuntos.innerHTML = "";

            adjuntosSeleccionados.forEach((file, index) => {
                const item = document.createElement("div");
                item.className = "adjunto_item";

                const nombre = document.createElement("span");
                nombre.className = "adjunto_nombre";
                nombre.textContent = file.name;

                const btnDel = document.createElement("button");
                btnDel.className = "btnAdjuntoDelete";
                btnDel.textContent = "❌";
                btnDel.onclick = () => {
                    eliminarAdjunto(index);
                };

                item.appendChild(nombre);
                item.appendChild(btnDel);
                listaAdjuntos.appendChild(item);
            });
        }

        // Eliminar adjunto específico
        function eliminarAdjunto(i) {
            adjuntosSeleccionados.splice(i, 1);
            actualizarListaAdjuntos();
        }



/* =========================================================
   LÓGICA DE ENVÍO Y VALIDACIÓN (REEMPLAZA TU FINAL ACTUAL)
   ========================================================= */

const form = document.getElementById("miFormulario");

if (form) {
    form.addEventListener("submit", function (e) {
        e.preventDefault(); // Detener envío automático


        // 1. Validar que exista al menos una evidencia
        const totalFotos = window.fotosCapturadas ? window.fotosCapturadas.length : 0;
        const totalVideos = window.videosCapturados ? window.videosCapturados.length : 0;
        const totalAudios = window.audiosCapturados ? window.audiosCapturados.length : 0;
        const totalAdjuntos = window.adjuntosSeleccionados ? window.adjuntosSeleccionados.length : 0;

        const tieneEvidencia = (totalFotos + totalVideos + totalAudios + totalAdjuntos) > 0;

        if (!tieneEvidencia) {
            alert("⚠️ Debe adjuntar o capturar al menos una evidencia (Foto, Video, Audio o Archivo) para poder enviar el reporte.");
            return; // Detiene el proceso aquí
        }

        // 2. Si hay evidencias, procedemos directamente al envío
        enviarFormulario();
    });
}

// 5. Función de Compresión
async function comprimirImagen(archivo, calidad = 0.7, maxWidth = 1280) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.readAsDataURL(archivo);
        reader.onload = (event) => {
            const img = new Image();
            img.src = event.target.result;
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;
                if (width > maxWidth) {
                    height *= maxWidth / width;
                    width = maxWidth;
                }
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                canvas.toBlob((blob) => {
                    const name = archivo.name ? archivo.name.replace(/\.[^/.]+$/, "") + ".jpg" : "foto.jpg";
                    resolve(new File([blob], name, { type: "image/jpeg" }));
                }, "image/jpeg", calidad);
            };
        };
    });
}

// 6. ENVÍO FINAL (FETCH ASYNC)
async function enviarFormulario() {
    const mensajeElement = document.getElementById("mensaje");
    if (mensajeElement) {
        mensajeElement.textContent = "⏳ Comprimiendo y enviando... no cierre la página.";
        mensajeElement.style.color = "orange";
    }

    const btnSubmit = form.querySelector('button[type="submit"]');
    if (btnSubmit) btnSubmit.disabled = true;

    const formData = new FormData(form);

    try {
        // Procesar Adjuntos Acumulados
        if (window.adjuntosSeleccionados) {
            for (let i = 0; i < window.adjuntosSeleccionados.length; i++) {
                let f = window.adjuntosSeleccionados[i];
                if (f.type.startsWith("image/")) {
                    f = await comprimirImagen(f, 0.7);
                }
                formData.append("adjunto_" + i, f);
            }
        }

        // Procesar Fotos Capturadas
        if (window.fotosCapturadas) {
            window.fotosCapturadas.forEach((blob, i) => {
                formData.append("foto_" + i, new File([blob], `foto_captura_${i}.jpg`, { type: "image/jpeg" }));
            });
        }

        // Procesar Videos
        if (window.videosCapturados) {
            window.videosCapturados.forEach((blob, i) => {
                formData.append("video_" + i, new File([blob], `video_${i}.webm`, { type: "video/webm" }));
            });
        }

        // Procesar Audios
        if (window.audiosCapturados) {
            window.audiosCapturados.forEach((blob, i) => {
                formData.append("audio_" + i, new File([blob], `audio_${i}.webm`, { type: "audio/webm" }));
            });
        }

        const res = await fetch("/Capturador_rep/submit", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            if (mensajeElement) {
                mensajeElement.textContent = "✅ " + (data.mensaje || "Guardado exitosamente");
                mensajeElement.style.color = "green";
            }
            setTimeout(() => location.reload(), 2500);
        } else {
            throw new Error(data.error || "Error en el servidor");
        }

    } catch (err) {
        console.error("Error en envío:", err);
        if (mensajeElement) {
            mensajeElement.textContent = "❌ Error: " + err.message;
            mensajeElement.style.color = "red";
        }
        if (btnSubmit) btnSubmit.disabled = false;
    }
}
