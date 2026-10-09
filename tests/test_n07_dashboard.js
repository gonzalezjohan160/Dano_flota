const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

class Element {
    constructor(tagName = "div") {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.listeners = {};
        this.value = "";
        this.className = "";
        this._text = "";
    }

    set textContent(value) {
        this._text = String(value);
        this.children = [];
    }

    get textContent() {
        return this._text + this.children.map(child => child.textContent).join("");
    }

    addEventListener(name, callback) {
        this.listeners[name] = callback;
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this._text = "";
        this.children = children;
    }
}

const xss = "<img src=x onerror=alert(1)>";
const jsonData = {
    "registros-json": [[2026, 10, 1, 2, 3, 4]],
    "costos-json": [[2026, 10, 200]],
    "valores-json": [[2026, 10, 100]],
    "operaciones-json": [[2026, 10, 50]],
    "heat-data-json": [[4.7, -74]],
    "rr-json": [[2026, 10, 4, 2]],
    "franjas-json": [["04:00-10:00", 2]],
    "ultimos-eventos-json": [
        { Movil: xss, Fecha_evento: "08/10/2026", Zona_dano: "ZONA", Parte_afectada: xss },
        { Movil: null, Fecha_evento: null, Zona_dano: null, Parte_afectada: null },
    ],
    "vehiculos-json": [[xss, xss, 12345], ["BUS-2", 2, null], ["BUS-3", 3, "no numérico"]],
};

const elements = Object.fromEntries(
    Object.entries(jsonData).map(([id, data]) => [id, { textContent: JSON.stringify(data) }])
);
for (const id of ["tbodyUltimosEventos", "tbodyVehiculos", "filtroMovil", "filtroVehiculo"]) {
    elements[id] = new Element(id);
}

const document = {
    getElementById: id => elements[id] || null,
    createElement: tagName => new Element(tagName),
    addEventListener(name, callback) {
        if (name === "DOMContentLoaded") this.ready = callback;
    },
};

let chartsCreated = 0;
let mapTilesCreated = 0;
let heatLayersCreated = 0;
function Chart() { chartsCreated += 1; }
const L = {
    map: () => ({ setView() { return this; }, invalidateSize() {} }),
    tileLayer: () => ({ addTo() { mapTilesCreated += 1; } }),
    heatLayer: () => ({ addTo() { heatLayersCreated += 1; } }),
};

const script = fs.readFileSync("Static/Script/Script_dashboard.js", "utf8");
vm.runInNewContext(script, {
    document, Chart, L, console, setTimeout, Intl, Number, String, Map, Set, Array, JSON,
});
document.ready();

assert.strictEqual(chartsCreated, 4);
assert.strictEqual(mapTilesCreated, 1);
assert.strictEqual(heatLayersCreated, 1);

const latestEvents = elements.tbodyUltimosEventos;
assert.strictEqual(latestEvents.children.length, 2);
assert.strictEqual(latestEvents.children[0].children[0].textContent, xss);
assert.strictEqual(latestEvents.children[0].children[3].textContent, xss);
assert(!latestEvents.children.some(row => row.children.some(cell => cell.tagName === "IMG")));

elements.filtroMovil.value = "<IMG";
elements.filtroMovil.listeners.keyup.call(elements.filtroMovil);
assert.strictEqual(latestEvents.children.length, 1);
elements.filtroMovil.value = "";
elements.filtroMovil.listeners.keyup.call(elements.filtroMovil);
assert.strictEqual(latestEvents.children.length, 2);

const vehicles = elements.tbodyVehiculos.children;
assert.strictEqual(vehicles.length, 3);
assert.strictEqual(vehicles[0].children[0].textContent, xss);
assert.strictEqual(vehicles[0].children[1].children[0].textContent, xss);
assert.strictEqual(
    vehicles[0].children[2].textContent,
    `$${(12345).toLocaleString("es-CO", { maximumFractionDigits: 0 })}`
);
assert.strictEqual(vehicles[1].children[2].textContent, "—");
assert.strictEqual(vehicles[2].children[2].textContent, "—");
assert(!vehicles.some(row => row.children.some(cell => cell.tagName === "IMG")));

elements.filtroVehiculo.value = "<IMG";
elements.filtroVehiculo.listeners.keyup.call(elements.filtroVehiculo);
assert.strictEqual(elements.tbodyVehiculos.children.length, 1);
elements.filtroVehiculo.value = "";
elements.filtroVehiculo.listeners.keyup.call(elements.filtroVehiculo);
assert.strictEqual(elements.tbodyVehiculos.children.length, 3);

console.log("N-07 Dashboard tests passed: text-only rendering, filters, null handling, currency and chart/map initialization.");
