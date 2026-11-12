const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

class Element {
    constructor(tagName) {
        this.tagName = tagName;
        this.children = [];
        this.classList = { add() {} };
        this.controls = false;
    }
    appendChild(child) { this.children.push(child); }
}

const created = [];
const document = {
    createElement(tagName) {
        const element = new Element(tagName);
        created.push(element);
        return element;
    },
};

const source = fs.readFileSync("Static/Script/Historicos_comun/duraciones_galeria.js", "utf8");
const start = source.indexOf("function renderGaleria(");
assert(start >= 0, "renderGaleria debe existir");
const context = { document, encodeURIComponent, String };
vm.runInNewContext(source.slice(start), context);

const gallery = new Element("div");
context.renderGaleria(gallery, [
    { Id: 1, TipoArchivo: "operaciones", FileName: "foto.jpg" },
    { Id: 2, TipoArchivo: "operaciones", FileName: "video.mp4" },
    { Id: 3, TipoArchivo: "operaciones", FileName: "audio.mp3" },
    { Id: 4, TipoArchivo: "operaciones", FileName: "archivo.svg" },
    { Id: 5, TipoArchivo: "operaciones", FileName: "<img src=x onerror=alert(1)>" },
]);

assert.deepStrictEqual(gallery.children.map(item => item.children[0].tagName), ["img", "video", "audio", "a", "a"]);
const unsafeFileLink = gallery.children[3].children[0];
assert.strictEqual(unsafeFileLink.download, "archivo.svg");
assert.strictEqual(unsafeFileLink.target, undefined);
assert.strictEqual(unsafeFileLink.rel, "noopener noreferrer");
assert.strictEqual(gallery.children[4].children[0].textContent, "<img src=x onerror=alert(1)>");
assert.strictEqual(gallery.children[4].children[0].download, "<img src=x onerror=alert(1)>");

for (const filename of ["Static/Script/Modulo_unificado/adjuntos.js", "Static/Script/Historico_danos/detalle.js"]) {
    const script = fs.readFileSync(filename, "utf8");
    assert(!/target\s*=\s*["']_blank["']/.test(script), `${filename} no debe abrir adjuntos en pestañas nuevas`);
    assert(script.includes(".download"), `${filename} debe ofrecer descarga para formatos no inline`);
}

console.log("Pruebas N-08 de galería aprobadas.");
