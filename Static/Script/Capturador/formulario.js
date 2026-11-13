// Capturador — campos del formulario (UF, móvil, código, ruta, tipología, conductor) y mapa de ubicación.
// Antes formaba parte de Script_captur.js; se carga en orden desde frontend/Formulario.html.

// Fecha del evento: el calendario no permite elegir una fecha u hora futura.
const fechaEventoInput = document.getElementById('Fecha');
if (fechaEventoInput) {
    const ahoraLocal = () => {
        const ahora = new Date();
        ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
        return ahora.toISOString().slice(0, 16);
    };
    fechaEventoInput.max = ahoraLocal();
    fechaEventoInput.addEventListener('focus', () => fechaEventoInput.max = ahoraLocal());
}

// Mayúsculas
const inputs = document.querySelectorAll('input[type="text"]');
inputs.forEach(input => input.addEventListener('input', () => input.value = input.value.toUpperCase()));

// Catálogos de la base (los arma el servidor en <script id="catalogos-json">):
// prefijo del móvil por UF, área por código de operador y rutas por UF.
const catalogos = JSON.parse(document.getElementById('catalogos-json')?.textContent || '{}');

// UF -> Móvil
const uf_Select = document.getElementById('UF_input');
const movil_Input = document.getElementById('Movil_input');
const movilesPor_UF = catalogos.prefijos_movil || {};
uf_Select.addEventListener('change', () => movil_Input.value = movilesPor_UF[uf_Select.value] || "");

// Código -> Área
const codigo_Select = document.getElementById('Codigo_input');
const Area_input = document.getElementById('Area_input');
const codigosPor_area = catalogos.areas_por_codigo || {};
codigo_Select.addEventListener('change', () => Area_input.value = codigosPor_area[codigo_Select.value] || catalogos.area_por_defecto || "");

// UF -> Rutas
const rutaSelect = document.getElementById('ruta_input');
const rutasPorUF = catalogos.rutas_por_uf || {};
uf_Select.addEventListener('change', () => {
    const rutas = rutasPorUF[uf_Select.value] || [];
    rutaSelect.innerHTML = '<option value="" disabled hidden>SELECCIONE LA RUTA</option>';
    rutas.forEach(r => {
        const option = document.createElement('option');
        option.value = r;
        option.textContent = r;
        rutaSelect.appendChild(option);
    });
});

// Tipología -> fetch (simulación)
const TiplogiaInput = document.getElementById('Tipologia_input');

movil_Input.addEventListener('change', async () => {
    const No_interno = movil_Input.value.trim();
    if (!No_interno) return;

    try {
        const res = await fetch(`/Capturador/getFlota?No_interno=${No_interno}`);
        const data = await res.json();

        if (!data || !data.movil_valido) {
            TiplogiaInput.value = '';
            alert('⚠️ No se encontró ningún móvil con ese número interno.');
            return;
        }

        TiplogiaInput.value = data.Tipologia_interno;

    } catch (err) {
        console.error(err);
        TiplogiaInput.value = '';
        alert('❌ Error al consultar la base de datos.');
    }
});

// Nombre -> fetch (simulación)
const nombreInput = document.getElementById('Nombre_input');

codigo_Select.addEventListener('change', async () => {
    const codigo = codigo_Select.value.trim();
    if (!codigo) return;

    try {
        const res = await fetch(`/Capturador/getConductor?codigo=${codigo}`);
        const data = await res.json();

        if (!data || !data.nombre) {
            nombreInput.value = '';
            alert('⚠️ No se encontró ningún conductor con ese código.');
            return;
        }

        nombreInput.value = data.nombre;

    } catch (err) {
        console.error(err);
        nombreInput.value = '';
        alert('❌ Error al consultar datos del conductor.');
    }
});
// Mapa y patios
const patioSelect = document.getElementById('Patio_input');
const latitud = document.getElementById('latitud');
const longitud = document.getElementById('longitud');
const direccionInput = document.getElementById('direccion');
const sugerencias = document.getElementById('sugerencias');
let marker;
const coords = {
    "Bilbao": { lat: 4.753461, lon: -74.121692 },
    "Gaitana": { lat: 4.741000, lon: -74.113273 },
    "san_Andres": { lat: 4.732344, lon: -74.130865 },
    "san_Bernardino": { lat: 4.629413, lon: -74.205624 },
    "Corpas": { lat: 4.763787, lon: -74.093375 },
    "Diana_Turbay": { lat: 4.544681, lon: -74.109096 }
};

const map = L.map('map').setView([4.65, -74.1], 12);
map.attributionControl.setPrefix(false);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors &middot; Open Database License (ODbL)'
}).addTo(map);

patioSelect.addEventListener('change', () => {
    const patio = patioSelect.value;
    if (!coords[patio]) return;
    const { lat, lon } = coords[patio];
    latitud.value = lat;
    longitud.value = lon;
    direccionInput.value = patio.replace("_", " ");
    if (marker) map.removeLayer(marker);
    const popup = document.createElement('b');
    popup.textContent = patio;
    marker = L.marker([lat, lon]).addTo(map).bindPopup(popup).openPopup();
    map.setView([lat, lon], 17);
});

// Autocompletado
let timeout;
direccionInput.addEventListener('input', () => {
    clearTimeout(timeout);
    // desmarcar patio si se escribe manual
    if(patioSelect.value !== '') {patioSelect.selectedIndex = 0;}
    sugerencias.innerHTML = '';
    const query = direccionInput.value.trim();
    if (query.length < 3) return;
    timeout = setTimeout(async () => {
        try {
            const res = await fetch(`/Capturador/geocode?q=${encodeURIComponent(query)}`);
            const resultados = await res.json();
            sugerencias.innerHTML = '';
            resultados.forEach(item => {
                const div = document.createElement('div');
                div.textContent = item.nombre;
                div.onclick = () => {
                    direccionInput.value = item.nombre;
                    // desmarcar seleccion de patio
                    patioSelect.selectedIndex = 0;
                    latitud.value = item.lat;
                    longitud.value = item.lon;
                    sugerencias.innerHTML = '';
                    if (marker) map.removeLayer(marker);
                    const popup = document.createElement('b');
                    popup.textContent = item.nombre;
                    marker = L.marker([item.lat, item.lon]).addTo(map).bindPopup(popup).openPopup();
                    map.setView([item.lat, item.lon], 17);
                };
                sugerencias.appendChild(div);
            });
        } catch (err) { console.warn(err); }
    }, 400);
});

// Click manual en mapa
map.on('click', e => {
    const { lat, lng } = e.latlng;
    // desmarcar patio
    patioSelect.selectedIndex = 0;
    if (marker) map.removeLayer(marker);
    marker = L.marker([lat, lng]).addTo(map);
    latitud.value = lat;
    longitud.value = lng;
    direccionInput.value = `Coordenadas: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
});
