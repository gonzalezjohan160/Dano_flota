const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
class Element {
    constructor(tag = 'div') { this.tagName = tag; this.children = []; this.style = {}; this.listeners = {}; this.value = ''; }
    set innerHTML(value) { this.children = []; }
    appendChild(child) { this.children.push(child); }
    append(...children) { this.children.push(...children); }
    setAttribute(key, value) { this[key] = value; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    reportValidity() { return true; }
}
const elements = {};
const doc = {
    getElementById(id) { return id === 'catalogos-json' ? null : (elements[id] ||= new Element()); },
    createElement(tag) { return new Element(tag); }
};
const archivos = [
    { Id: 1, FileName: 'foto.JPG', TipoArchivo: 'operaciones' },
    { Id: 2, FileName: 'mtto.jpg', TipoArchivo: 'mtto' },
    { Id: 3, FileName: 'svial.png', TipoArchivo: 'svial' },
    { Id: 4, FileName: 'documento.pdf', TipoArchivo: 'operaciones' },
    { Id: 5, FileName: 'video.mp4', TipoArchivo: 'operaciones' }
];
let lightbox = 0;
let enviado;
const context = {
    document: doc, window: {}, CFG: { propia: 'oper', modulo: 'Operaciones' },
    performance: { now: () => 0 }, console: { log() {}, error() {} },
    abrirLightbox: () => { lightbox++; }, renderDetalle() {}, filtrarTabla() {}, alert() {},
    FormData: class { constructor() { this.campos = {}; } append(k, v) { this.campos[k] = v; } },
    csrfFetch: async (url, opciones) => {
        enviado = { url, body: opciones.body };
        return { json: async () => ({ status: 'error', message: 'prueba sin guardar' }) };
    }
};
vm.createContext(context);
for (const nombre of ['edicion_evento', 'adjuntos']) {
    vm.runInContext(fs.readFileSync(`Static/Script/Modulo_unificado/${nombre}.js`, 'utf8'), context);
}
function tarjetas() { return elements.galeriaAdjuntos.children.filter(c => c.className === 'adjunto-item'); }
function botones() { return tarjetas().flatMap(t => t.children.filter(c => c.tagName === 'button')); }

(async () => {
    context.prepararEdicionEvento({ Id: 7, archivos_count: 5, caso_cerrado: false }, {}, {});
    context.renderGaleria(archivos);
    assert.strictEqual(botones().length, 0, 'sin X en modo lectura');
    context.mostrarAccionesEdicion(true);
    assert.strictEqual(botones().length, 1, 'solo imagen de Operaciones');
    assert.strictEqual(botones()[0].textContent, '×');
    let detenido = 0;
    botones()[0].onclick({ preventDefault() {}, stopPropagation() { detenido++; } });
    assert.strictEqual(detenido, 1);
    assert.strictEqual(lightbox, 0);
    assert.strictEqual(tarjetas().length, 4);
    context.iniciarEdicionEvento();
    doc.getElementById('motivo_modificacion').value = 'Imagen duplicada';
    await elements.btn_guardar_modificacion.listeners.click();
    assert.strictEqual(enviado.url, '/Operaciones/actualizar_evento/7');
    assert.deepStrictEqual(JSON.parse(enviado.body.campos.archivos_eliminar), [1]);
    assert.strictEqual(elements.btn_guardar_modificacion.disabled, false);
    // Cancelar restaura las miniaturas y descarta la seleccion pendiente.
    elements.btn_cancelar_modificacion.listeners.click();
    assert.strictEqual(tarjetas().length, 5);
    assert.strictEqual(botones().length, 0);
    assert.strictEqual(vm.runInContext('imagenesEdicionEliminar.size', context), 0);
    // Un caso cerrado nunca ofrece eliminacion.
    context.prepararEdicionEvento({ Id: 8, caso_cerrado: true }, {}, {});
    context.renderGaleria(archivos);
    context.mostrarAccionesEdicion(true);
    assert.strictEqual(botones().length, 0);
    console.log('OK: X en edicion solo para imagenes de Operaciones; envio, cancelacion y casos cerrados.');
})().catch(error => { console.error(error); process.exitCode = 1; });
