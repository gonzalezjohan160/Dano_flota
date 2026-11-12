// Módulo unificado — Galería de adjuntos y modal de detalle/adjuntos.
// Antes formaba parte de Script_oper.js; el orden de carga está en frontend/parciales/modulo_unificado/_scripts.html.

//======================================================
// RENDER GALERÍA
//======================================================

function renderGaleria(archivos) {

    const inicioArchivos = performance.now();
    const galeria = document.getElementById("galeriaAdjuntos");
    galeria.innerHTML = "";
    archivosGaleriaActuales = archivos.slice();
    const visibles = archivos.filter(file => !edicionImagenesActiva || !imagenesEdicionEliminar.has(Number(file.Id)));

    if (!visibles.length && !imagenesEdicionEliminar.size) {
        galeria.innerHTML = `<p style="text-align:center;color:#777">Sin archivos adjuntos</p>`;
        console.log(`[Ver archivos] Archivos - construir e insertar DOM: ${(performance.now() - inicioArchivos).toFixed(2)} ms (sin archivos)`);
        return;
    }

    if (edicionImagenesActiva && imagenesEdicionEliminar.size) {
        const aviso = document.createElement("p");
        aviso.className = "galeria-aviso-eliminacion";
        aviso.textContent = "Las imágenes marcadas se eliminarán al guardar información. Cancelar conserva las imágenes.";
        galeria.appendChild(aviso);
    }

    visibles.forEach(file => {

        const div = document.createElement("div");
        div.className = "adjunto-item";

        const nombreArchivo = String(file.FileName || "Adjunto");
        const ext = nombreArchivo.includes(".")
            ? nombreArchivo.split(".").pop().toLowerCase()
            : "";

        const url = `/archivo/${encodeURIComponent(file.Id)}?tipo=${encodeURIComponent(file.TipoArchivo)}`;

        if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext)) {
            const img = document.createElement("img");
            img.src = url;
            img.onclick = () => abrirLightbox(url);
            div.appendChild(img);
            if (edicionImagenesActiva && CFG.propia === "oper" && file.TipoArchivo === "operaciones") {
                const eliminar = document.createElement("button");
                eliminar.type = "button";
                eliminar.className = "adjunto-eliminar-imagen";
                eliminar.textContent = "×";
                eliminar.setAttribute("aria-label", `Eliminar imagen ${nombreArchivo}`);
                eliminar.title = "Marcar imagen para eliminar al guardar";
                eliminar.onclick = event => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (!edicionImagenesActiva) return;
                    imagenesEdicionEliminar.add(Number(file.Id));
                    renderGaleria(archivosGaleriaActuales);
                };
                div.appendChild(eliminar);
            }
        } else if (["mp4", "webm"].includes(ext)) {
            const video = document.createElement("video");
            video.src = url;
            video.controls = true;
            div.appendChild(video);
        } else if (["mp3", "ogg", "wav"].includes(ext)) {
            const audio = document.createElement("audio");
            audio.src = url;
            audio.controls = true;
            div.appendChild(audio);
        } else {
            const a = document.createElement("a");
            a.href = url;
            a.download = nombreArchivo;
            a.rel = "noopener noreferrer";
            a.textContent = nombreArchivo;
            div.appendChild(a);
        }

        galeria.appendChild(div);
    });

    console.log(`[Ver archivos] Archivos - construir e insertar DOM: ${(performance.now() - inicioArchivos).toFixed(2)} ms (${archivos.length} archivos)`);
}

//======================================================
// MODAL ADJUNTOS
//======================================================

window.mostrarAdjuntos = async function (id) {

    const inicioTotal = performance.now();
    // Si el usuario abre otro evento, la carga anterior queda invalidada.
    const solicitudActual = ++solicitudDetalleActual;

    const registro = registros.find(r => r.Id == id);
    if (!registro) return;
    eventoEdicionActual = null;
    edicionImagenesActiva = false;
    imagenesEdicionEliminar.clear();
    archivosGaleriaActuales = [];

    movilSeleccionado = id;

    const inicioModal = performance.now();
    const modal = document.getElementById("modalAdjuntos");
    const tituloRegistro = document.getElementById("modal_registro1");

    if (!modal) {
        console.error("[Ver archivos] No existe #modalAdjuntos en el DOM");
        return;
    }

    if (!tituloRegistro) {
        console.error("[Ver archivos] No existe #modal_registro1 en el DOM");
        return;
    }

    modal.style.display = "block";
    renderGaleria([]);
    tituloRegistro.textContent = `#${registro.Id}`;


    console.log(`[Ver archivos] Abrir modal: ${id}:${(performance.now() - inicioModal).toFixed(2)} ms`);

    try {
        const inicioFetch = performance.now();
        const response = await fetch(`/${CFG.modulo}/detalle/${id}`);

        console.log(
        `[Ver archivos] Fetch #${id}: ${(performance.now() - inicioFetch).toFixed(2)} ms (HTTP ${response.status})`);

        if(!response.ok){throw new Error(`HTTP ${response.status}`);}
        const inicioJson = performance.now();
        const data = await response.json();

        console.log(`[Ver archivos] response.json() #${id}: ${(performance.now() - inicioJson).toFixed(2)} ms`);

        //Si mientras esperábamos la respuesta el usuario
        // abrió otro evento, esta respuesta ya no sirve.

        if (solicitudActual !== solicitudDetalleActual){console.log(`[Ver archivos] Respuesta ignorada. ` + `Evento #${id} ya no es el evento activo.`);
        return;
        }
        const inicioRender = performance.now();

         // renderDetalle es async, por lo tanto debemos esperar
        // a que termine antes de continuar.
        await renderDetalle(registro, data);

        // Volvemos a comprobar porque renderDetalle()
        // contiene operaciones asíncronas (geocodificación).
        if (solicitudActual !== solicitudDetalleActual){console.log(`[Ver archivos] Render ignorado. ` + `Evento #${id} ya no es el evento activo.`);
        return;
        }
        prepararEdicionEvento(registro,data.registro ?? {},data);

        // Junta los 4 conjuntos de archivos que puede ver el módulo

        const todosArchivos = [
        ...(data.archivos ?? []),
        ...(SECCIONES_VISIBLES.has("mtto")
            ? (data.archivos_mtto ?? [])
            : []),
        ...(SECCIONES_VISIBLES.has("svial")
            ? (data.archivos_svial ?? [])
            : []),
        ...(SECCIONES_VISIBLES.has("laboral")
            ? (data.archivos_laboral ?? [])
            : [])
        ];

        renderGaleria(todosArchivos);

        console.log(
        `[Ver archivos] Render completo #${id}: ` +
        `${(performance.now() - inicioRender).toFixed(2)} ms`
        );

        console.log(
        `[Ver archivos] Total #${id}: ` +
        `${(performance.now() - inicioTotal).toFixed(2)} ms`
        );

    } catch (error) {
        if (solicitudActual !== solicitudDetalleActual) {
        console.log(`[Ver archivos] Error de solicitud anterior ignorado para #${id}`);
        return;
        }
        console.error( `[Ver archivos] Error cargando evento #${id}:`,error);
        alert("Error cargando el evento.");
    }
};

window.cerrarModalAdjuntos = function () {
    eventoEdicionActual = null;
    edicionImagenesActiva = false;
    imagenesEdicionEliminar.clear();
    document.getElementById("modalAdjuntos").style.display = "none";
};


// Acciones de arranque de esta parte, en el orden original (las llama inicio.js).
function iniciarAdjuntos() {
    // Esta parte no tiene acciones de arranque.
}
