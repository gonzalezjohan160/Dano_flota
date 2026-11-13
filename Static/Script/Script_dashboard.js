document.addEventListener('DOMContentLoaded', function () {
    const getJSON = (id) => {
        const el = document.getElementById(id);
        if (!el) return [];
        try {
            const datos = JSON.parse(el.textContent);
            return Array.isArray(datos) ? datos : [];
        } catch (error) {
            console.error(`No fue posible leer los datos del Dashboard (${id}).`, error);
            return [];
        }
    };

    const registros = getJSON('registros-json');
    const mantenimiento = getJSON('mantenimiento-json');
    const valores = getJSON('valores-json');
    const operaciones = getJSON('operaciones-json');
    const heatData = getJSON('heat-data-json');
    const rrll = getJSON('rr-json');
    const franjas = getJSON('franjas-json');
    const ultimosEventos = getJSON('ultimos-eventos-json');
    const vehiculosData = getJSON('vehiculos-json');

    // GRÁFICA 1: BARRAS
    if (registros.length > 0) {
        new Chart(document.getElementById('barChart1'), {
            type: 'bar',
            data: {
                labels: registros.map(r => `${r[0]}-${String(r[1]).padStart(2, '0')}`),
                datasets: [
                    { label: 'R. Laborales', data: registros.map(r => r[2]), backgroundColor: '#4f46e5' },
                    { label: 'Mantenimiento', data: registros.map(r => r[3]), backgroundColor: '#10b981' },
                    { label: 'Operaciones', data: registros.map(r => r[4]), backgroundColor: '#f59e0b' },
                    { label: 'S.Vial', data: registros.map(r => r[5]), backgroundColor: '#0bf5ab' }
                ]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }

    // GRÁFICA 2: LÍNEAS (FINANCIERA)
    if (operaciones.length > 0 || valores.length > 0) {

        // Helper: arma un mapa "YYYY-MM" -> valor a partir de las filas [año, mes, valor]
        const buildMap = (rows) => {
            const map = new Map();
            rows.forEach(r => {
                const key = `${r[0]}-${String(r[1]).padStart(2, '0')}`;
                map.set(key, r[2]);
            });
            return map;
        };

        const mapOperaciones = buildMap(operaciones);
        const mapValores = buildMap(valores);

        // Unión de todas las claves año-mes presentes en cualquiera de las 2 series
        const allKeys = new Set([
            ...mapOperaciones.keys(),
            ...mapValores.keys()
        ]);

        // Ordenamos cronológicamente
        const labels = Array.from(allKeys).sort();

        // Cada serie se rellena con 0 (o null si prefieres un hueco visual) donde falte el mes
        const dataOperaciones = labels.map(k => mapOperaciones.get(k) ?? 0);
        const dataValores = labels.map(k => mapValores.get(k) ?? 0);

        new Chart(document.getElementById('barChart2'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Costo Operaciones', data: dataOperaciones, borderColor: '#f59e0b', fill: false, tension: 0.3 },
                    { label: 'Valor Conciliado', data: dataValores, borderColor: '#3b82f6', fill: false, tension: 0.3 }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: { ticks: { callback: (v) => '$' + v.toLocaleString() } }
                }
            }
        });
    }
    
    if (mantenimiento.length > 0) {
        new Chart(document.getElementById('lineChartCostoDano'), {
            type: 'line',
            data: {
                labels: mantenimiento.map(r => `${r[0]}-${String(r[1]).padStart(2, '0')}`),
                datasets: [{ label: 'Costo Mantenimiento', data: mantenimiento.map(r => r[2]),
                    borderColor: '#ef4444', fill: false, tension: 0.3 }]
            },
            options: {
                responsive: true,
                scales: { y: { ticks: { callback: v => '$' + v.toLocaleString() } } }
            }
        });
    }

    // GRÁFICA 3: BARRAS (RRLL)

    if (rrll.length > 0) {
        const labelsRRLL = rrll.map(r => `${r[0]}-${String(r[1]).padStart(2, '0')}`);
        const totalCasos = rrll.map(r => r[2]);
        const casosCerrados = rrll.map(r => r[3]);

        new Chart(document.getElementById('barChartRRLL'), {
            type: 'bar',
            data: { labels: labelsRRLL, datasets: [{ label: 'Total Casos', data: totalCasos, backgroundColor: '#3b82f6' }, { label: 'Casos Cerrados', data: casosCerrados, backgroundColor: '#10b981' }] },

            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }

    // GRÁFICA 4: LÍNEA (FRANJAS HORARIAS)

    if (franjas.length > 0) {
        new Chart(document.getElementById('lineChartFranjas'), {
            type: 'line',
            data: {
                labels: franjas.map(f => f[0]),
                datasets: [{ label: 'Cantidad Eventos', data: franjas.map(f => f[1]), borderColor: '#33d772', fill: true, tension: 0.3, pointRadius: 5, pointHoverRadius: 7 }]
            },
            options: {
                responsive: true, plugins: { legend: { position: 'bottom' } },
                scales: {
                    y: {
                        ticks: {
                            stepSize: 1, beginAtZero: true

                        }
                    }
                }
            }

        });

    }


    // MAPA
    const map = L.map('map').setView([4.7110, -74.0721], 11);
    map.attributionControl.setPrefix(false);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors &middot; Open Database License (ODbL)'
    }).addTo(map);

    if (heatData.length > 0) {
        L.heatLayer(heatData, { radius: 25, blur: 15, maxZoom: 17 }).addTo(map);
    }

    setTimeout(() => map.invalidateSize(), 500);

    const filtroMovil = document.getElementById("filtroMovil");
    const tbodyUltimosEventos = document.getElementById("tbodyUltimosEventos");

    function renderUltimosEventos(datos) {

        tbodyUltimosEventos.replaceChildren();

        (Array.isArray(datos) ? datos : []).forEach(evento => {

            const fila = document.createElement("tr");

            const valores = [
            evento?.Movil,
            evento?.Fecha_evento,
            evento?.Zona_dano,
            evento?.Parte_afectada
            ];

            valores.forEach(valor => {
            const celda = document.createElement("td");
            celda.textContent = valor == null ? "" : String(valor);
            fila.appendChild(celda);
            });

            tbodyUltimosEventos.appendChild(fila);
        })
    }

    renderUltimosEventos(ultimosEventos);

    filtroMovil.addEventListener("keyup", function () {

        const texto = this.value.trim().toUpperCase();

        if (texto === "") {

            renderUltimosEventos(ultimosEventos);
            return;
        }

        const filtrados = ultimosEventos.filter(evento =>
            String(evento?.Movil ?? "").toUpperCase().includes(texto)
        );

        renderUltimosEventos(filtrados);

    });

    // TABLA: EVENTOS POR VEHÍCULO
    const filtroVehiculo = document.getElementById("filtroVehiculo");
    const tbodyVehiculos = document.getElementById("tbodyVehiculos");

    function renderVehiculos(datos) {

        tbodyVehiculos.replaceChildren();

        (Array.isArray(datos) ? datos : []).forEach(vehiculo => {
            const valoresVehiculo = Array.isArray(vehiculo) ? vehiculo : [];
            const fila = document.createElement("tr");

            // Móvil
            const celdaMovil = document.createElement("td");
            celdaMovil.textContent =
                valoresVehiculo[0] == null ? "" : String(valoresVehiculo[0]);
            fila.appendChild(celdaMovil);

            // Cantidad de eventos
            const celdaEventos = document.createElement("td");
            celdaEventos.className = "text-center";

            const badge = document.createElement("span");
            badge.className = "badge";
            badge.textContent =
                valoresVehiculo[1] == null ? "" : String(valoresVehiculo[1]);

            celdaEventos.appendChild(badge);
            fila.appendChild(celdaEventos);

            // Costo
            const celdaCosto = document.createElement("td");
            celdaCosto.className = "text-right text-danger";

            const valorCosto = valoresVehiculo[2];
            const costo = (typeof valorCosto === "number" ||
                (typeof valorCosto === "string" && valorCosto.trim() !== ""))
                ? Number(valorCosto)
                : NaN;
            celdaCosto.textContent = Number.isFinite(costo)
                ? `$${costo.toLocaleString("es-CO", { maximumFractionDigits: 0 })}`
                : "—";

            fila.appendChild(celdaCosto);
            tbodyVehiculos.appendChild(fila);
        })
    }

    if (filtroVehiculo && tbodyVehiculos) {

        renderVehiculos(vehiculosData);

        filtroVehiculo.addEventListener("keyup", function () {

            const texto = this.value.trim().toUpperCase();

            if (texto === "") {

                renderVehiculos(vehiculosData);
                return;
            }

            const filtrados = vehiculosData.filter(vehiculo =>
                String(Array.isArray(vehiculo) ? vehiculo[0] ?? "" : "").toUpperCase().includes(texto)
            );

            renderVehiculos(filtrados);

        });
    }

});
