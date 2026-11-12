// Capturador — cámara siempre activa y captura de fotos con carrusel.
// Antes formaba parte de Script_captur.js; se carga en orden desde frontend/Formulario.html.

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
