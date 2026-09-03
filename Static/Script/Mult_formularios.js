    /***********************
     * CARGA DE REGISTROS
     ***********************/
    try {
        const script = document.getElementById('registros-json');
        registros = JSON.parse(script.textContent);
    } catch (e) {
        console.error("Error al parsear registros:", e);
    }  
  
    /***********************
     * LIGHTBOX
     ***********************/
    let imagenesLightbox = [];
    let indiceImagenLightbox = -1;

    function actualizarLightbox() {
        const lightbox = document.getElementById('lightbox');
        const img = document.getElementById('lightbox-img');
        const anterior = document.getElementById('lightbox-anterior');
        const siguiente = document.getElementById('lightbox-siguiente');
        img.src = imagenesLightbox[indiceImagenLightbox];
        anterior.style.display = indiceImagenLightbox > 0 ? '' : 'none';
        siguiente.style.display = indiceImagenLightbox < imagenesLightbox.length - 1 ? '' : 'none';
        lightbox.style.display = 'flex';
    }

    window.abrirLightbox = (url) => {
        imagenesLightbox = Array.from(document.querySelectorAll('.galeria img')).map(img => img.src);
        indiceImagenLightbox = imagenesLightbox.indexOf(new URL(url, window.location.origin).href);
        if (indiceImagenLightbox < 0) {
            imagenesLightbox = [url];
            indiceImagenLightbox = 0;
        }
        actualizarLightbox();
    }

    window.navegarLightbox = (direccion) => {
        const siguienteIndice = indiceImagenLightbox + direccion;
        if (siguienteIndice < 0 || siguienteIndice >= imagenesLightbox.length) return;
        indiceImagenLightbox = siguienteIndice;
        actualizarLightbox();
    }

    window.cerrarLightbox = () => {
        const lightbox = document.getElementById('lightbox');
        const img = document.getElementById('lightbox-img');
        img.src = '';
        imagenesLightbox = [];
        indiceImagenLightbox = -1;
        lightbox.style.display = 'none';
    }

    /***********************
     * MAPA
     ***********************/
    let map = null;
    let marker = null;

    window.initMapaModal = () => {
        const mapDiv = document.getElementById("map");
        if (!mapDiv) return;

        // 🔥 destruir mapa previo
        if (map) {
            map.remove();
            map = null;
        }

        map = L.map(mapDiv).setView([4.65, -74.1], 12);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors"
        }).addTo(map);
    };

    window.actualizarMapaModal = (coords) => {
        if (!map || !coords) return;

        setTimeout(() => {
            map.invalidateSize(true);

            if (marker) {
                marker.remove();
                marker = null;
            }

            marker = L.marker([coords.lat, coords.lon])
                .addTo(map)
                .bindPopup("Ubicación del evento")
                .openPopup();

            map.setView([coords.lat, coords.lon], 17);
        }, 200);
    };


        // ================= COORDENADAS =================
    function obtenerCoordsDesdeDireccion(direccion) {
        if (!direccion) return null;
        const partes = direccion.split(",");
        if (partes.length !== 2) return null;

        const lat = parseFloat(partes[0].trim());
        const lon = parseFloat(partes[1].trim());
        if (isNaN(lat) || isNaN(lon)) return null;

        return { lat, lon };
    }

    /***********************
     * FILTROS
     ***********************/
    window.filtrarTabla = function () {
        const tabla = document.getElementById("tabla-registros");
        const filas = tabla.querySelectorAll("tbody tr");
        const filtros = document.querySelectorAll("thead th input");

        const ufSeleccionada = document.getElementById("filtroUF")?.value || "todos";

        filas.forEach(fila => {
            const celdas = fila.querySelectorAll("td");
            let mostrar = true;

            // ---- filtro UF (col 2 = MÓVIL / ajusta si es otra)
            if (ufSeleccionada !== "todos") {
                const ufFila = fila.dataset.uf;
                if (String(ufFila) !== ufSeleccionada) mostrar = false;
            }

            // ---- filtros por columnas
            filtros.forEach(input => {
                if (!mostrar) return;
                if (input.disabled) return;

                const col = input.dataset.col;
                if (col === undefined) return;

                const filtro = input.value.trim().toLowerCase();
                if (!filtro) return;

                let contenido = celdas[col]?.innerText.trim().toLowerCase() || "";

                if (input.type === "date") {
                    contenido = convertirTablaAISO(contenido);
                }

                if (!contenido.includes(filtro)) {
                    mostrar = false;
                }
            });

            fila.style.display = mostrar ? "" : "none";
        });
    };

    /***********************
     * FESTIVOS COLOMBIA 🇨🇴
     ***********************/

    // Cache por año (mejor rendimiento)
    const festivosPorAnio = {};

    // Pascua
    function calcularPascua(year) {
        const a = year % 19;
        const b = Math.floor(year / 100);
        const c = year % 100;
        const d = Math.floor(b / 4);
        const e = b % 4;
        const f = Math.floor((b + 8) / 25);
        const g = Math.floor((b - f + 1) / 3);
        const h = (19 * a + b - d - g + 15) % 30;
        const i = Math.floor(c / 4);
        const k = c % 4;
        const l = (32 + 2 * e + 2 * i - h - k) % 7;
        const m = Math.floor((a + 11 * h + 22 * l) / 451);
        const month = Math.floor((h + l - 7 * m + 114) / 31);
        const day = ((h + l - 7 * m + 114) % 31) + 1;
        return new Date(year, month - 1, day);
    }

    // Mover festivos al lunes (Ley Emiliani)
    function moverALunes(fecha) {
        const d = fecha.getDay();
        if (d === 1) return fecha;
        const f = new Date(fecha);
        f.setDate(fecha.getDate() + ((8 - d) % 7));
        return f;
    }

    // Generar festivos Colombia
    function generarFestivosColombia(year) {
        const festivos = [];

        // Fijos
        festivos.push(new Date(year, 0, 1));    // Año Nuevo
        festivos.push(new Date(year, 4, 1));    // Día del Trabajo
        festivos.push(new Date(year, 6, 20));   // Independencia
        festivos.push(new Date(year, 7, 7));    // Boyacá
        festivos.push(new Date(year, 11, 8));   // Inmaculada
        festivos.push(new Date(year, 11, 25));  // Navidad

        // Emiliani
        festivos.push(moverALunes(new Date(year, 0, 6)));   // Reyes
        festivos.push(moverALunes(new Date(year, 2, 19)));  // San José
        festivos.push(moverALunes(new Date(year, 5, 29)));  // San Pedro y San Pablo
        festivos.push(moverALunes(new Date(year, 7, 15)));  // Asunción
        festivos.push(moverALunes(new Date(year, 9, 12)));  // Raza
        festivos.push(moverALunes(new Date(year, 10, 1)));  // Todos los Santos
        festivos.push(moverALunes(new Date(year, 10, 11))); // Cartagena

        // Pascua
        const pascua = calcularPascua(year);
        festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 3)); // Jueves Santo
        festivos.push(new Date(year, pascua.getMonth(), pascua.getDate() - 2)); // Viernes Santo
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 43))); // Ascensión
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 64))); // Corpus
        festivos.push(moverALunes(new Date(year, pascua.getMonth(), pascua.getDate() + 71))); // Sagrado

        return festivos.map(f => f.toISOString().split("T")[0]);
    }

    // Obtener festivos por año
    function obtenerFestivosColombia(year) {
        if (!festivosPorAnio[year]) {
            festivosPorAnio[year] = generarFestivosColombia(year);
        }
        return festivosPorAnio[year];
    }

    /***********************
     * DÍAS HÁBILES
     ***********************/
    function esDiaHabil(fecha) {
        const dia = fecha.getDay();
        if (dia === 0 || dia === 6) return false; // domingo o sábado

        const iso = fecha.toISOString().split("T")[0];
        const festivos = obtenerFestivosColombia(fecha.getFullYear());

        return !festivos.includes(iso);
    }

    /***********************
     * DURACIÓN HÁBIL
     ***********************/
    function calcularDuracionHabil(inicio, fin) {
        let actual = new Date(inicio);
        let totalMs = 0;

        while (actual < fin) {
            if (esDiaHabil(actual)) {
                let finDia = new Date(actual);
                finDia.setHours(23, 59, 59, 999);
                if (finDia > fin) finDia = fin;
                totalMs += (finDia - actual);
            }
            actual.setDate(actual.getDate() + 1);
            actual.setHours(0, 0, 0, 0);
        }

        const dias = Math.floor(totalMs / 86400000);
        const horas = Math.floor((totalMs % 86400000) / 3600000);
        const minutos = Math.floor((totalMs % 3600000) / 60000);

        return { dias, horas, minutos };
    }

    // Eliminar adjunto específico
    function eliminarAdjunto(i) {
        adjuntosSeleccionados.splice(i, 1);
        actualizarListaAdjuntos();
    }

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

        // Selecciona todos los textarea
    const textareas = document.querySelectorAll('textarea');

    // Convierte a mayúsculas mientras se escribe
    textareas.forEach(textarea => {
        textarea.addEventListener('input', () => {
            textarea.value = textarea.value.toUpperCase();
        });
    });

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
                    const fechaEvento = new Date(registro.fecha + "T00:00:00");
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

        try {
            const [anio, mes, dia] = fecha.split("-");
            return `${dia}/${mes}/${anio}`;
        } catch {
            return "Sin fecha";
        }
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

        const ext = file.FileName.split('.').pop().toLowerCase();
        const url = "/Historico_movil/ver_archivo?path=" + encodeURIComponent(file.FilePath);

        if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
            const img = document.createElement('img');
            img.src = url;
            if (typeof abrirLightbox === "function") {
                img.onclick = () => abrirLightbox(url);
            }
            div.appendChild(img);

        } else if (['mp4','mov','avi','webm'].includes(ext)) {
            const video = document.createElement('video');
            video.src = url;
            video.controls = true;
            div.appendChild(video);

        } else {
            const link = document.createElement('a');
            link.href = url;
            link.target = '_blank';
            link.textContent = file.FileName;
            div.appendChild(link);
        }

        galeria.appendChild(div);
    });
}
