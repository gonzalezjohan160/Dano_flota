// Módulo unificado — Cierre de ventanas, lightbox de imágenes y arranque: llama a cada iniciar...() en orden.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// CERRAR MODALES AL HACER CLICK AFUERA
//======================================================

window.onclick = function (event) {
    const modalFormulario = document.getElementById("miModal");
    const modalAdjuntos = document.getElementById("modalAdjuntos");

    if (event.target === modalFormulario) cerrarModal();
    if (event.target === modalAdjuntos) cerrarModalAdjuntos();
};

//======================================================
// LIGHTBOX
//======================================================

let imagenesLightbox = [];
let indiceImagenLightbox = -1;

function actualizarLightbox() {
    document.getElementById("lightbox-img").src = imagenesLightbox[indiceImagenLightbox];
    document.getElementById("lightbox-anterior").style.display = indiceImagenLightbox > 0 ? "" : "none";
    document.getElementById("lightbox-siguiente").style.display = indiceImagenLightbox < imagenesLightbox.length - 1 ? "" : "none";
    document.getElementById("lightbox").style.display = "flex";
}

window.abrirLightbox = function (url) {
    imagenesLightbox = Array.from(document.querySelectorAll(".galeria img")).map(img => img.src);
    indiceImagenLightbox = imagenesLightbox.indexOf(new URL(url, window.location.origin).href);
    if (indiceImagenLightbox < 0) {
        imagenesLightbox = [url];
        indiceImagenLightbox = 0;
    }
    actualizarLightbox();
};

window.navegarLightbox = function (direccion) {
    const siguienteIndice = indiceImagenLightbox + direccion;
    if (siguienteIndice < 0 || siguienteIndice >= imagenesLightbox.length) return;
    indiceImagenLightbox = siguienteIndice;
    actualizarLightbox();
};

window.cerrarLightbox = function () {
    document.getElementById("lightbox").style.display = "none";
    document.getElementById("lightbox-img").src = "";
    imagenesLightbox = [];
    indiceImagenLightbox = -1;
};


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarVentanas() {
    //======================================================
    // ESC CERRAR MODAL
    //======================================================

    document.addEventListener("keydown", e => {
        if (e.key === "Escape") {
            cerrarModal();
            cerrarModalAdjuntos();
        }
    });

    //======================================================
    // INICIALIZACIÓN
    //======================================================

    console.log("===================================");
    console.log("Módulo cargado:", CFG.modulo);
    console.log("Sección propia:", CFG.propia);
    console.log("Secciones visibles:", CFG.seccionesVisibles);
    console.log("===================================");
}


//======================================================
// DOM READY: arranque en el mismo orden que el bloque original
//======================================================

document.addEventListener("DOMContentLoaded", () => {

    if (!CFG) {
        console.error("No existe configuración para:", MODULO);
        return;
    }

    iniciarConfiguracion();
    iniciarUtilidades();
    iniciarFiltros();
    iniciarTabla();
    iniciarDetalle();
    iniciarEdicionEvento();
    iniciarAdjuntos();
    iniciarFormulario();
    iniciarFormularioCampos();
    iniciarFlujoOperaciones();
    iniciarValidacion();
    iniciarEnvio();
    iniciarVentanas();

});
