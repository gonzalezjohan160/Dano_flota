        // Mayúsculas
        const inputs = document.querySelectorAll('input[type="text"]');
        inputs.forEach(input => input.addEventListener('input', () => input.value = input.value.toUpperCase()));

        // UF -> Móvil
        const uf_Select = document.getElementById('UF_input');
        const movil_Input = document.getElementById('Movil_input');
        const movilesPor_UF = { "10": "Z32-", "16": "Z34-" };
        uf_Select.addEventListener('change', () => movil_Input.value = movilesPor_UF[uf_Select.value] || "");


        // Tipología -> fetch (simulación)
        const TiplogiaInput = document.getElementById('Tipologia_input');

        movil_Input.addEventListener('change', async () => {
            const No_interno = movil_Input.value.trim();
            if (!No_interno) return;

            try {
                const res = await fetch(`/Capturador_rep/getFlota?No_interno=${No_interno}`);
                const data = await res.json();

                if (!data || !data.Tipologia_interno) {
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

        // ===== Formateo del costo =====
        const visible = document.getElementById('Costo_id');
        const hidden = document.getElementById('Costo_real');
        visible.addEventListener('input', () => {
            let value = visible.value.replace(/[^\d]/g, '');
            hidden.value = value;
            visible.value = value ? new Intl.NumberFormat('es-CO', {
                style: 'currency',
                currency: 'COP',
                minimumFractionDigits: 0
            }).format(parseInt(value, 10)) : '';
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
                mediaRecorderVideo = new MediaRecorder(recordingStream);

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