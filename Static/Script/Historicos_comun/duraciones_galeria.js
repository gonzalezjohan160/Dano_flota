// Historicos comun — duraciones del registro, formato del costo y galería de adjuntos.
// Antes formaba parte de Mult_formularios.js; se carga en orden desde frontend/Front_historico_danos.html y frontend/Front_historico_movil.html.

    /***********************
     * DURACIÓN HÁBIL
     ***********************/

    window.calcularDuracionesRegistro = (registro) => {
        let duracion = "Desconocida";
        let duracionEvento = "Desconocida";
        let t = null;

        const convertirFechaRegistro = (fecha) => {
            const [fechaParte, horaParte] = fecha.split(" ");
            const [dia, mes, anio] = fechaParte.split("/");
            return new Date(`${anio}-${mes}-${dia}T${horaParte || "00:00:00"}`);
        };

        if (registro?.fecha_r) {
            try {
                const fechaInicio = convertirFechaRegistro(registro.fecha_r);
                const casoCerrado = Number(registro.estado_caso) === 1;
                const fechaFinal = casoCerrado
                    ? convertirFechaRegistro(registro.fecha_cierre || "")
                    : new Date();

                if (!isNaN(fechaInicio) && !isNaN(fechaFinal)) {
                    t = calcularDuracionHabil(fechaInicio, fechaFinal);
                    duracion = `${t.dias}d ${t.horas}h`;
                }

                if (registro.fecha) {
                    const fechaEvento = new Date(registro.fecha);
                    if (!isNaN(fechaEvento) && !isNaN(fechaFinal)) {
                        const tEvento = calcularDuracionHabil(fechaEvento, fechaFinal);
                        duracionEvento = `${tEvento.dias}d ${tEvento.horas}h`;
                    }
                }
            } catch (err) {
                console.error("❌ Error fechas:", err);
            }
        }

        return { duracion, duracionEvento, t };
    };


    /***********************
     * FORMATEO FECHA REGISTRO
     ***********************/
        window.formatearFechaRegistro = (fecha) => {
        if (!fecha) return "Sin fecha";

        const str = String(fecha).trim();

        // Formato DD/MM/YYYY o DD/MM/YYYY HH:mm:ss
        if (/^\d{2}\/\d{2}\/\d{4}/.test(str)) {
            return str.substring(0, 10);
        }

        // Formato YYYY-MM-DD o YYYY-MM-DD HH:mm:ss
        const m = str.match(/^(\d{4})-(\d{2})-(\d{2})/);

        if (m) {
            return `${m[3]}/${m[2]}/${m[1]}`;
        }
        return "Sin fecha";
    };

        /***********************
     * FORMATEO FECHA REGISTRO varios
     ***********************/
    const formatoFechaHora = v =>
        v
            ? new Intl.DateTimeFormat("es-CO", {
                timeZone: "UTC",
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true
            }).format(new Date(v))
        : "-";

                /***********************
     * FORMATEO FECHA REGISTRO HISTORICO
     ***********************/
    const formatoFecha = v =>
        v
            ? new Intl.DateTimeFormat("es-CO", {
                timeZone: "UTC",
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
            }).format(new Date(v))
        : "-";


        // ===== Formateo del costo =====
    const visible = document.getElementById('Costo_id');
    const hidden = document.getElementById('Costo_real');

    if (visible && hidden) { // <--- Esta es la "llave" de seguridad
        visible.addEventListener('input', () => {
            let value = visible.value.replace(/[^\d]/g, '');
            hidden.value = value;
            visible.value = value ? new Intl.NumberFormat('es-CO', {
                style: 'currency',
                currency: 'COP',
                minimumFractionDigits: 0
            }).format(parseInt(value, 10)) : '';
        });
    }

    // ===== VISUALIZACIÓN DE GALERIA =====
function renderGaleria(galeria, archivos) {

    galeria.innerHTML = '';

    if (!archivos || archivos.length === 0) {
        galeria.innerHTML = '<p style="text-align:center; color:#777;">Sin archivos adjuntos</p>';
        return;
    }

    archivos.forEach(file => {

        const div = document.createElement('div');
        div.classList.add('adjunto-item');

        const nombreArchivo = String(file.FileName || "Adjunto");
        const ext = nombreArchivo.includes(".")
            ? nombreArchivo.split(".").pop().toLowerCase()
            : "";
        const url = "/archivo/" + encodeURIComponent(file.Id) + "?tipo=" + encodeURIComponent(file.TipoArchivo);

        if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
            const img = document.createElement('img');
            img.src = url;
            if (typeof abrirLightbox === "function") {
                img.onclick = () => abrirLightbox(url);
            }
            div.appendChild(img);

        } else if (['mp4','webm'].includes(ext)) {
            const video = document.createElement('video');
            video.src = url;
            video.controls = true;
            div.appendChild(video);

        } else if (['mp3','ogg','wav'].includes(ext)) {
            const audio = document.createElement('audio');
            audio.src = url;
            audio.controls = true;
            div.appendChild(audio);

        } else {
            const link = document.createElement('a');
            link.href = url;
            link.download = nombreArchivo;
            link.rel = 'noopener noreferrer';
            link.textContent = nombreArchivo;
            div.appendChild(link);
        }

        galeria.appendChild(div);
    });
}
