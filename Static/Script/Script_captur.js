// Mayúsculas
const inputs = document.querySelectorAll('input[type="text"]');
inputs.forEach(input => input.addEventListener('input', () => input.value = input.value.toUpperCase()));

// UF -> Móvil
const uf_Select = document.getElementById('UF_input');
const movil_Input = document.getElementById('Movil_input');
const movilesPor_UF = { "10": "Z32-", "16": "Z34-" };
uf_Select.addEventListener('change', () => movil_Input.value = movilesPor_UF[uf_Select.value] || "");

// Código -> Área
const codigo_Select = document.getElementById('Codigo_input');
const Area_input = document.getElementById('Area_input');
const codigosPor_area = { 1: "MANTENIMIENTO", 2: "OPERACIONES", 3: "LAVADO", 4: "CAPACITACIÓN OBZ", 5: "TERCERO", 6: "TANQUEO", 7:"ADMINISTRATIVO" };
codigo_Select.addEventListener('change', () => Area_input.value = codigosPor_area[codigo_Select.value] || "OBZ");

// UF -> Rutas
const rutaSelect = document.getElementById('ruta_input');
const rutasPorUF = {
    "10": ["CG147", "DG208", "CA127", "CH131", "CA129", "CA124", "TRANSITO A PATIO", "PATIO"],
    "16": ["CL149", "CB144", "CG137", "CA134", "CB138", "CA151", "CF154", "CA153", "CB145", "TRANSITO A PATIO", "PATIO"]
};
uf_Select.addEventListener('change', () => {
    const rutas = rutasPorUF[uf_Select.value] || [];
    rutaSelect.innerHTML = '<option value="" disabled hidden>SELECCIONE LA RUTA</option>';
    rutas.forEach(r => {
        const option = document.createElement('option');
        option.value = r;
        option.textContent = r;
        rutaSelect.appendChild(option);
    });
});

// Tipología -> fetch (simulación)
const TiplogiaInput = document.getElementById('Tipologia_input');

movil_Input.addEventListener('change', async () => {
    const No_interno = movil_Input.value.trim();
    if (!No_interno) return;

    try {
        const res = await fetch(`/Capturador/getFlota?No_interno=${No_interno}`);
        const data = await res.json();

        if (!data || !data.movil_valido) {
            TiplogiaInput.value = '';
            alert('⚠️ No se encontró ningún móvil con ese número interno.');
            return;
        }

        TiplogiaInput.value = data.Tipologia_interno;

    } catch (err) {
        console.error(err);
        TiplogiaInput.value = '';
        alert('❌ Error al consultar la base de datos.');
    }
});

// Nombre -> fetch (simulación)
const nombreInput = document.getElementById('Nombre_input');

codigo_Select.addEventListener('change', async () => {
    const codigo = codigo_Select.value.trim();
    if (!codigo) return;

    try {
        const res = await fetch(`/Capturador/getConductor?codigo=${codigo}`);
        const data = await res.json();

        if (!data || !data.nombre) {
            nombreInput.value = '';
            alert('⚠️ No se encontró ningún conductor con ese código.');
            return;
        }

        nombreInput.value = data.nombre;

    } catch (err) {
        console.error(err);
        nombreInput.value = '';
        alert('❌ Error al consultar datos del conductor.');
    }
});
// Mapa y patios
const patioSelect = document.getElementById('Patio_input');
const latitud = document.getElementById('latitud');
const longitud = document.getElementById('longitud');
const direccionInput = document.getElementById('direccion');
const sugerencias = document.getElementById('sugerencias');
let marker;
const coords = {
    "Bilbao": { lat: 4.753461, lon: -74.121692 },
    "Gaitana": { lat: 4.741000, lon: -74.113273 },
    "san_Andres": { lat: 4.732344, lon: -74.130865 },
    "san_Bernardino": { lat: 4.629413, lon: -74.205624 },
    "Corpas": { lat: 4.763787, lon: -74.093375 },
    "Diana_Turbay": { lat: 4.544681, lon: -74.109096 }
};

const map = L.map('map').setView([4.65, -74.1], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors' }).addTo(map);

patioSelect.addEventListener('change', () => {
    const patio = patioSelect.value;
    if (!coords[patio]) return;
    const { lat, lon } = coords[patio];
    latitud.value = lat;
    longitud.value = lon;
    direccionInput.value = patio.replace("_", " ");
    if (marker) map.removeLayer(marker);
    marker = L.marker([lat, lon]).addTo(map).bindPopup(`<b>${patio}</b>`).openPopup();
    map.setView([lat, lon], 17);
});

// Autocompletado
let timeout;
direccionInput.addEventListener('input', () => {
    clearTimeout(timeout);
    // desmarcar patio si se escribe manual
    if(patioSelect.value !== '') {patioSelect.selectedIndex = 0;} 
    sugerencias.innerHTML = '';
    const query = direccionInput.value.trim();
    if (query.length < 3) return;
    timeout = setTimeout(async () => {
        try {
            const res = await fetch(`/Capturador/geocode?q=${encodeURIComponent(query)}`);
            const resultados = await res.json();
            sugerencias.innerHTML = '';
            resultados.forEach(item => {
                const div = document.createElement('div');
                div.textContent = item.nombre;
                div.onclick = () => {
                    direccionInput.value = item.nombre;
                    // desmarcar seleccion de patio
                    patioSelect.selectedIndex = 0;
                    latitud.value = item.lat;
                    longitud.value = item.lon;
                    sugerencias.innerHTML = '';
                    if (marker) map.removeLayer(marker);
                    marker = L.marker([item.lat, item.lon]).addTo(map).bindPopup(`<b>${item.nombre}</b>`).openPopup();
                    map.setView([item.lat, item.lon], 17);
                };
                sugerencias.appendChild(div);
            });
        } catch (err) { console.warn(err); }
    }, 400);
});

// Click manual en mapa
map.on('click', e => {
    const { lat, lng } = e.latlng;
    // desmarcar patio
    patioSelect.selectedIndex = 0; 
    if (marker) map.removeLayer(marker);
    marker = L.marker([lat, lng]).addTo(map);
    latitud.value = lat;
    longitud.value = lng;
    direccionInput.value = `Coordenadas: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
});

/* =========================================================
CAMARA - SIEMPRE ACTIVA (solo video para visor)
========================================================= */
let previewStream = null;
const camara = document.getElementById("camara");

// Iniciar cámara trasera al cargar (sin audio)
async function iniciarCamaraPreview() {
    if (previewStream) return;

    try {
        // Intentamos usar la cámara trasera (solo móviles)
        const constraints = {
            video: { facingMode: "environment" },
            audio: false
        };

        previewStream = await navigator.mediaDevices.getUserMedia(constraints);
        camara.srcObject = previewStream;
        camara.play();

    } catch (err1) {
        console.warn("Cámara trasera no disponible. Intentando cámara por defecto…");

        try {
            // Para PC o fallback general
            previewStream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: false
            });

            camara.srcObject = previewStream;
            camara.play();

        } catch (err2) {
            console.error("No se pudo activar ninguna cámara:", err2);
        }
    }
}
iniciarCamaraPreview();

/* =========================================================
FOTOS - captura usando el stream del visor
========================================================= */
window.fotosCapturadas = [];
let fotoIndex = 0;

function mostrarFoto() {
    const img = document.getElementById("fotoActual");
    const btnDelete = document.getElementById("btnDeleteFoto");

    if (fotosCapturadas.length === 0) {
        img.style.display = "none";
        btnDelete.style.display = "none";
        return;
    }

    img.src = URL.createObjectURL(fotosCapturadas[fotoIndex]);
    img.style.display = "block";
    btnDelete.style.display = "block";
}

// Tomar foto con marca de agua (formato 24h)
document.getElementById('btnTomarFoto').onclick = () => {
    if (!previewStream) return;

    const canvas = document.createElement('canvas');
    canvas.width = camara.videoWidth;
    canvas.height = camara.videoHeight;

    const ctx = canvas.getContext('2d');

    // 1️⃣ Dibujar imagen original
    ctx.drawImage(camara, 0, 0, canvas.width, canvas.height);

    // 2️⃣ Fecha en formato 24 horas
    const fecha = new Date();
    const marca = fecha.toLocaleString("es-CO", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false   // ← FORMATO 24 HORAS
    });

    ctx.font = "40px Arial";
    ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
    ctx.strokeStyle = "rgba(0, 0, 0, 0.8)";
    ctx.lineWidth = 3;

    const x = 20;
    const y = canvas.height - 40;

    ctx.strokeText(marca, x, y);
    ctx.fillText(marca, x, y);

    // 3️⃣ Guardar como Blob
    canvas.toBlob(blob => {
        fotosCapturadas.push(blob);
        fotoIndex = fotosCapturadas.length - 1;
        mostrarFoto();
    }, "image/jpeg", 0.7);
};


// Carrusel de fotos
document.getElementById("btnPrevFoto").onclick = () => {
    if (fotosCapturadas.length === 0) return;
    fotoIndex = (fotoIndex - 1 + fotosCapturadas.length) % fotosCapturadas.length;
    mostrarFoto();
};
document.getElementById("btnNextFoto").onclick = () => {
    if (fotosCapturadas.length === 0) return;
    fotoIndex = (fotoIndex + 1) % fotosCapturadas.length;
    mostrarFoto();
};

// Borrar foto
document.getElementById("btnDeleteFoto").onclick = () => {
    if (fotosCapturadas.length === 0) return;
    fotosCapturadas.splice(fotoIndex, 1);
    if (fotoIndex >= fotosCapturadas.length) fotoIndex--;
    mostrarFoto();
};

/* =========================================================
VIDEO - grabación con audio solo durante grabación
========================================================= */
let mediaRecorderVideo;
let chunksVideo = [];

// NUEVO: arreglo para guardar TODOS los videos
window.videosCapturados = [];
let videoIndex = 0;

// Cronómetro de video
let timerInterval = null;
let segundosGrabados = 0;

function iniciarTimer() {
    segundosGrabados = 0;
    const timer = document.getElementById("camara_timer");
    timer.style.display = "block";

    function actualizar() {
        segundosGrabados++;
        const min = String(Math.floor(segundosGrabados / 60)).padStart(2, "0");
        const sec = String(segundosGrabados % 60).padStart(2, "0");
        timer.textContent = `${min}:${sec}`;
    }

    timerInterval = setInterval(actualizar, 1000);
    actualizar();
}

function detenerTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
    document.getElementById("camara_timer").style.display = "none";
}

/* =========================================================
VISOR DE VIDEOS (tipo carrusel, igual que fotos)
========================================================= */
function mostrarVideo() {
    const visor = document.getElementById("videoActual");
    const btnDelete = document.getElementById("btnDeleteVideo");

    if (videosCapturados.length === 0) {
        visor.style.display = "none";
        btnDelete.style.display = "none";
        return;
    }

    visor.src = URL.createObjectURL(videosCapturados[videoIndex]);
    visor.style.display = "block";
    btnDelete.style.display = "block";
    visor.load();
}

/* =========================================================
Iniciar grabación de video
========================================================= */
document.getElementById("btnStartVideo").onclick = async () => {
    try {
        if (!previewStream) return;

        // Activar solo durante grabación: obtener micrófono
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Crear stream para grabación (video + audio)
        const recordingStream = new MediaStream([
            ...previewStream.getVideoTracks(),
            ...audioStream.getAudioTracks()
        ]);

        chunksVideo = [];
        mediaRecorderVideo = new MediaRecorder(recordingStream, {
            mimeType: 'video/webm; codecs=vp8,opus',
            videoBitsPerSecond: 1000000 // <--- LIMITA A 1 Mbps (Suficiente para reportes)
        });

        mediaRecorderVideo.ondataavailable = e => chunksVideo.push(e.data);

        mediaRecorderVideo.onstop = () => {
            const blob = new Blob(chunksVideo, { type: "video/webm; codecs=vp8,opus" });

            // NUEVO: guardar video en lista
            videosCapturados.push(blob);
            videoIndex = videosCapturados.length - 1;
            mostrarVideo();

            // Detener audioStream al finalizar
            audioStream.getTracks().forEach(track => track.stop());
        };

        mediaRecorderVideo.start();
        document.getElementById("camara_recordDot").style.display = "block";
        iniciarTimer();
        document.getElementById("btnStartVideo").disabled = true;
        document.getElementById("btnStopVideo").disabled = false;
    } catch (err) {
        console.error("Error al iniciar grabación de video:", err);
    }
};

/* =========================================================
Detener grabación
========================================================= */
document.getElementById("btnStopVideo").onclick = () => {
    if (!mediaRecorderVideo) return;
    mediaRecorderVideo.stop();
    document.getElementById("camara_recordDot").style.display = "none";
    detenerTimer();
    document.getElementById("btnStartVideo").disabled = false;
    document.getElementById("btnStopVideo").disabled = true;
};

/* =========================================================
Controles del carrusel
========================================================= */
// Anterior
document.getElementById("btnPrevVideo").onclick = () => {
    if (videosCapturados.length === 0) return;
    videoIndex = (videoIndex - 1 + videosCapturados.length) % videosCapturados.length;
    mostrarVideo();
};

// Siguiente
document.getElementById("btnNextVideo").onclick = () => {
    if (videosCapturados.length === 0) return;
    videoIndex = (videoIndex + 1) % videosCapturados.length;
    mostrarVideo();
};

// Eliminar
document.getElementById("btnDeleteVideo").onclick = () => {
    if (videosCapturados.length === 0) return;

    videosCapturados.splice(videoIndex, 1);

    if (videoIndex >= videosCapturados.length) {
        videoIndex = videosCapturados.length - 1;
    }

    mostrarVideo();
};

/* =========================================================
AUDIO - con temporizador + punto rojo + opción de borrar
========================================================= */
let mediaRecorderAudio;
let chunksAudio = [];
window.audiosCapturados = [];

let audioTimerInterval = null;
let audioSegundos = 0;

// 🔴 Elemento del timer
const audioTimer = document.getElementById("audio_timer");

/* ---------- INICIAR TEMPORIZADOR ---------- */
function iniciarAudioTimer() {
    audioSegundos = 0;
    audioTimer.style.display = "block";

    function tick() {
        audioSegundos++;

        const min = String(Math.floor(audioSegundos / 60)).padStart(2, "0");
        const sec = String(audioSegundos % 60).padStart(2, "0");

        audioTimer.innerHTML = `● ${min}:${sec}`;
    }

    tick();
    audioTimerInterval = setInterval(tick, 1000);
}

/* ---------- DETENER TEMPORIZADOR ---------- */
function detenerAudioTimer() {
    clearInterval(audioTimerInterval);
    audioTimerInterval = null;
    audioTimer.style.display = "none";
}

/* ---------- ACTUALIZAR LISTA DE AUDIOS ---------- */
function actualizarListaAudios() {
    const lista = document.getElementById("lista_audios");
    lista.innerHTML = "";

    audiosCapturados.forEach((blob, index) => {
        const item = document.createElement("div");
        item.className = "audio_item";

        const audio = document.createElement("audio");
        audio.controls = true;
        audio.src = URL.createObjectURL(blob);

        const btnDel = document.createElement("button");
        btnDel.className = "audio_delete_btn";
        btnDel.textContent = "❌";

        btnDel.onclick = () => borrarAudio(index);

        item.appendChild(audio);
        item.appendChild(btnDel);
        lista.appendChild(item);
    });
}

/* ---------- ELIMINAR AUDIO ---------- */
function borrarAudio(index) {
    audiosCapturados.splice(index, 1);
    actualizarListaAudios();
}

/* ---------- BOTÓN INICIAR AUDIO ---------- */
document.getElementById("btnStartAudio").onclick = async () => {
    try {
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

        chunksAudio = [];
        mediaRecorderAudio = new MediaRecorder(audioStream, {
            audioBitsPerSecond: 64000 // <--- 64 kbps es perfecto para voz humana
        });

        mediaRecorderAudio.ondataavailable = e => chunksAudio.push(e.data);

        mediaRecorderAudio.onstop = () => {
            const blob = new Blob(chunksAudio, { type: "audio/webm" });
            audiosCapturados.push(blob);

            actualizarListaAudios();

            audioStream.getTracks().forEach(track => track.stop());

            detenerAudioTimer();
        };

        mediaRecorderAudio.start();

        // Cambiar botones
        document.getElementById("btnStartAudio").disabled = true;
        document.getElementById("btnStopAudio").disabled = false;

        // Iniciar temporizador
        iniciarAudioTimer();

    } catch (err) {
        console.error("❌ Error al iniciar audio:", err);
    }
};

/* ---------- BOTÓN DETENER AUDIO ---------- */
document.getElementById("btnStopAudio").onclick = () => {
    if (!mediaRecorderAudio) return;

    mediaRecorderAudio.stop();

    document.getElementById("btnStartAudio").disabled = false;
    document.getElementById("btnStopAudio").disabled = true;
};

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

    modal.innerHTML = `
        <div style="background:white; padding:25px; border-radius:12px; width:320px; text-align:center; font-family:sans-serif;">
            <h3 style="color:#d9534f;">⚠ Registro Duplicado</h3>
            <p>Ya existe un reporte para el móvil <b>${movil}</b> en esta fecha con la zona de daño <b>${zona_dano}</b>.</p>
            <div style="margin-top:20px;">
                <button id="btnCancelarModal" style="padding:10px; cursor:pointer;">Cancelar</button>
                <button id="btnForzarEnvio" style="background:#d9534f; color:white; padding:10px; border:none; border-radius:5px; cursor:pointer;">Enviar de todos modos</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    document.getElementById("btnCancelarModal").onclick = () => modal.remove();
    document.getElementById("btnForzarEnvio").onclick = () => {
        modal.remove();
        enviarFormulario();
    };
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
