const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
let resultado = [];
const elements = { filtroEstado: { value: 'comite' } };
const contexto = {
    CFG: { propia: 'laboral' }, window: {}, console,
    document: { querySelectorAll: () => [], getElementById: id => elements[id] || null },
    renderTabla: filas => { resultado = filas; },
    registros: [
        { Id: 1, pendiente_proceso_actual: 'COMITE', caso_cerrado: false },
        { Id: 2, pendiente_proceso_actual: 'OPERACIONES, COMITE', caso_cerrado: false },
        { Id: 3, pendiente_proceso_actual: 'COMITE', caso_cerrado: true, cerrado_por_laboral: true },
        { Id: 4, pendiente_proceso_actual: 'COMPLETO', caso_cerrado: false },
        { Id: 5, pendiente_proceso_actual: 'OPERACIONES', caso_cerrado: false },
        { Id: 6, pendiente_proceso_actual: 'PRECOMITE', caso_cerrado: false }
    ]
};
vm.createContext(contexto);
for (const archivo of ['utilidades', 'filtros']) {
    vm.runInContext(fs.readFileSync(`Static/Script/Modulo_unificado/${archivo}.js`, 'utf8'), contexto);
}
function filtrar(estado, esperados) {
    elements.filtroEstado.value = estado;
    contexto.filtrarTabla();
    assert.deepStrictEqual(Array.from(resultado, r => r.Id), esperados);
}
filtrar('comite', [1, 2]);
filtrar('pendientes', [5, 6]);
filtrar('gestionados', [4]);
filtrar('cerrados', [3]);
filtrar('todos', [1, 2, 3, 4, 5, 6]);
contexto.registros[0].pendiente_proceso_actual = 'COMPLETO';
filtrar('comite', [2]);
vm.runInContext(fs.readFileSync('Static/Script/Modulo_unificado/envio.js', 'utf8'), contexto);
contexto.document.querySelector = () => ({ value: 'NO' });
elements.estado_caso = { value: 'COMITE' };
elements.filtroEstado.value = 'gestionados';
contexto.actualizarEstadoLocal(4);
assert.strictEqual(contexto.registros.find(r => r.Id === 4).pendiente_proceso_actual, 'COMITE');
assert.deepStrictEqual(Array.from(resultado, r => r.Id), [1]);
filtrar('comite', [2, 4]);
console.log('OK: filtro Comite, combinaciones, cierre y ultimo estado actualizado.');
