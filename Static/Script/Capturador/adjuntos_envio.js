// Capturador — adjuntos, validación de duplicados, compresión de imágenes y envío del formulario.
// Antes formaba parte de Script_captur.js; se carga en orden desde frontend/Formulario.html.

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
   LÓGICA DE ENVÍO Y VALIDACIÓN (FINAL DEL SCRIPT)
   ========================================================= */

// 1. Referencia al formulario
const form = document.getElementById("miFormulario");

// 2. Escuchar el evento submit
if (form) {
    form.addEventListener("submit", function (e) {
        e.preventDefault(); // Detener envío automático
        validarDuplicado();
    });
}

// 3. Función de Validación
function validarDuplicado() {
    const fecha = document.getElementById("Fecha").value;
    const movil = document.getElementById("Movil_input").value;
    const codigo = document.getElementById("Codigo_input").value;
    const zona_dano = document.getElementById("Zona_dano_input").value;

    if (!fecha || !movil || !codigo || !zona_dano) {
        alert("⚠️ Por favor complete Fecha, Móvil, Código y Zona de Daño antes de enviar.");
        return;
    }

// 2. NUEVA VALIDACIÓN: Verificar si hay al menos una evidencia
    const totalFotos = window.fotosCapturadas ? window.fotosCapturadas.length : 0;
    const totalVideos = window.videosCapturados ? window.videosCapturados.length : 0;
    const totalAudios = window.audiosCapturados ? window.audiosCapturados.length : 0;
    const totalAdjuntos = window.adjuntosSeleccionados ? window.adjuntosSeleccionados.length : 0;

    const tieneEvidencia = (totalFotos + totalVideos + totalAudios + totalAdjuntos) > 0;

    if (!tieneEvidencia) {
        alert("⚠️ Debe adjuntar o capturar al menos una evidencia (Foto, Video, Audio o Archivo) para poder enviar el reporte.");
        return; // Detiene el envío
    }

    fetch(`/Capturador/getFlota?No_interno=${encodeURIComponent(movil)}`)
        .then(res => res.json())
        .then(data => {
            if (!data || !data.movil_valido) {
                alert("El número de vehículo ingresado no es válido.");
                return;
            }

            fetch(`/Capturador/validarDuplicado?fecha=${encodeURIComponent(fecha)}&movil=${encodeURIComponent(movil)}&codigo=${encodeURIComponent(codigo)}&zona_dano=${encodeURIComponent(zona_dano)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.duplicado) {
                        mostrarModalDuplicado(fecha, movil, codigo, zona_dano);
                    } else {
                        enviarFormulario(); // Si no hay duplicado, procede al envío
                    }
                })
                .catch(err => {
                    console.error("Error validando:", err);
                    enviarFormulario(); // En caso de error de red, intentamos enviar de todos modos
                });
        })
        .catch(err => {
            console.error("Error validando móvil:", err);
            alert("❌ Error al consultar la base de datos.");
        });
}

// 4. Modal para Duplicados
function mostrarModalDuplicado(fecha, movil, codigo, zona_dano) {
    const existing = document.getElementById("modalDuplicado");
    if (existing) existing.remove();

    const modal = document.createElement("div");
    modal.id = "modalDuplicado";
    modal.style.cssText = `
        position:fixed; top:0; left:0; width:100%; height:100%;
        background:rgba(0,0,0,0.7); display:flex;
        align-items:center; justify-content:center; z-index:99999;
    `;

    const contenido = document.createElement("div");
    contenido.style.cssText = "background:white; padding:25px; border-radius:12px; width:320px; text-align:center; font-family:sans-serif;";

    const titulo = document.createElement("h3");
    titulo.style.color = "#d9534f";
    titulo.textContent = "⚠ Registro Duplicado";
    contenido.appendChild(titulo);

    const mensaje = document.createElement("p");
    mensaje.append("Ya existe un reporte para el móvil ");
    const movilTexto = document.createElement("b");
    movilTexto.textContent = movil;
    mensaje.appendChild(movilTexto);
    mensaje.append(" en esta fecha con la zona de daño ");
    const zonaTexto = document.createElement("b");
    zonaTexto.textContent = zona_dano;
    mensaje.appendChild(zonaTexto);
    mensaje.append(".");
    contenido.appendChild(mensaje);

    const acciones = document.createElement("div");
    acciones.style.marginTop = "20px";

    const btnCancelar = document.createElement("button");
    btnCancelar.id = "btnCancelarModal";
    btnCancelar.style.cssText = "padding:10px; cursor:pointer;";
    btnCancelar.textContent = "Cancelar";

    const btnForzar = document.createElement("button");
    btnForzar.id = "btnForzarEnvio";
    btnForzar.style.cssText = "background:#d9534f; color:white; padding:10px; border:none; border-radius:5px; cursor:pointer;";
    btnForzar.textContent = "Enviar de todos modos";

    acciones.append(btnCancelar, btnForzar);
    contenido.appendChild(acciones);
    modal.appendChild(contenido);
    document.body.appendChild(modal);
    btnCancelar.addEventListener("click", () => modal.remove());
    btnForzar.addEventListener("click", () => {
        modal.remove();
        enviarFormulario();
    });
}

// 5. Función de Compresión (Soporte para enviarFormulario)
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
    mensajeElement.textContent = "⏳ Comprimiendo y enviando... no cierre la página.";
    mensajeElement.style.color = "orange";

    // Bloquear botón para evitar doble clic
    const btnSubmit = form.querySelector('button[type="submit"]');
    if (btnSubmit) btnSubmit.disabled = true;

    const formData = new FormData(form);

    try {
        // Procesar Adjuntos
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
            for (let i = 0; i < window.fotosCapturadas.length; i++) {
                const file = new File([window.fotosCapturadas[i]], `foto_captura_${i}.jpg`, { type: "image/jpeg" });
                formData.append("foto_" + i, file);
            }
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

        const res = await fetch("/Capturador/submit", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            mensajeElement.textContent = "✅ " + (data.mensaje || "Guardado exitosamente");
            mensajeElement.style.color = "green";
            setTimeout(() => location.reload(), 2500);
        } else {
            throw new Error(data.error || "Error en el servidor");
        }

    } catch (err) {
        console.error("Error en envío:", err);
        mensajeElement.textContent = "❌ Error: " + err.message;
        mensajeElement.style.color = "red";
        if (btnSubmit) btnSubmit.disabled = false;
    }
}
