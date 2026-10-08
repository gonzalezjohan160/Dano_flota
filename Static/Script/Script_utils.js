// Escape text before inserting it into an HTML string.
window.escaparHtml = function (valor) {
    return String(valor ?? "").replace(/[&<>"']/g, caracter => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;"
    })[caracter]);
};

// Delegación para reemplazar manejadores inline en las páginas con CSP estricta.
document.addEventListener("click", event => {
    const control = event.target.closest("[data-csp-action]");
    if (!control) return;

    const acciones = {
        "cerrar-modal-adjuntos": () => window.cerrarModalAdjuntos?.(),
        "cerrar-modal": () => window.cerrarModal?.(),
        "cerrar-lightbox": () => window.cerrarLightbox?.(),
        "lightbox-anterior": () => window.navegarLightbox?.(-1),
        "lightbox-siguiente": () => window.navegarLightbox?.(1),
        "ejecutar-busqueda": () => window.ejecutarBusqueda?.(),
        "aplicar-filtros": () => window.aplicarFiltrosHistorico?.(),
        "descargar-excel": () => window.descargarExcelHistorico?.(),
        "pagina-anterior": () => window.irPaginaAnterior?.(),
        "pagina-siguiente": () => window.irPaginaSiguiente?.()
    };

    acciones[control.dataset.cspAction]?.();
});
