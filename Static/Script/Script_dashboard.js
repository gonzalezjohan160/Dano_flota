document.addEventListener('DOMContentLoaded', function() {
    const getJSON = (id) => {
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : [];
    };

    const registros = getJSON('registros-json');
    const costos = getJSON('costos-json');
    const valores = getJSON('valores-json');
    const heatData = getJSON('heat-data-json');
    const rrll = getJSON('rr-json');
    const franjas = getJSON('franjas-json');

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
            options: { responsive: true,  plugins: { legend: { position: 'bottom' } } }
        });
    }

    // GRÁFICA 2: LÍNEAS (FINANCIERA)
    if (costos.length > 0) {
        new Chart(document.getElementById('barChart2'), {
            type: 'line',
            data: {
                labels: costos.map(c => `${c[0]}-${String(c[1]).padStart(2, '0')}`),
                datasets: [
                    { label: 'Costo Daños', data: costos.map(c => c[2]), borderColor: '#ef4444', fill: false, tension: 0.3 },
                    { label: 'Valor Conciliado', data: valores.map(v => v[2]), borderColor: '#3b82f6', fill: false, tension: 0.3 }
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

    // GRÁFICA 3: BARRAS (RRLL)

    if (rrll.length > 0) {
        const labelsRRLL = rrll.map(r => `${r[0]}-${String(r[1]).padStart(2, '0')}`);
        const totalCasos = rrll.map(r => r[2]);
        const casosCerrados = rrll.map(r => r[3]);

        new Chart(document.getElementById('barChartRRLL'), {
            type: 'bar',
            data: {labels: labelsRRLL, datasets: [{ label: 'Total Casos', data: totalCasos, backgroundColor: '#3b82f6' }, { label: 'Casos Cerrados', data: casosCerrados, backgroundColor: '#10b981' }]},

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
            options: { responsive: true, plugins: { legend: { position: 'bottom' } },
                scales: {
                    y: { ticks: { stepSize: 1, beginAtZero: true 

                        } 
                    }
                }
            }

        });
        
     }


    // MAPA
    const map = L.map('map').setView([4.7110, -74.0721], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    if (heatData.length > 0) {
        L.heatLayer(heatData, { radius: 25, blur: 15, maxZoom: 17 }).addTo(map);
    }
    
    setTimeout(() => map.invalidateSize(), 500);
});