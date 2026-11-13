// Historicos comun — carga de registros, lightbox, mapa del modal y coordenadas.
// Antes formaba parte de Mult_formularios.js; se carga en orden desde frontend/Front_historico_danos.html y frontend/Front_historico_movil.html.

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
        map.attributionControl.setPrefix(false);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; OpenStreetMap contributors &middot; Open Database License (ODbL)'
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
