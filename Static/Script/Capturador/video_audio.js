// Capturador — grabación de video y de audio.
// Antes formaba parte de Script_captur.js; se carga en orden desde frontend/Formulario.html.

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
