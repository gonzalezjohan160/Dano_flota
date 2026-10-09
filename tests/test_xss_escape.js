const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const document = { addEventListener() {} };
const window = {};
const source = fs.readFileSync("Static/Script/Script_utils.js", "utf8");
vm.runInNewContext(source, { document, window });

for (const payload of [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>'
]) {
    const encoded = window.escaparHtml(payload);
    assert(!encoded.includes("<"), "El resultado no debe contener etiquetas interpretables");
    assert(!encoded.includes(">"), "El resultado debe codificar los cierres de etiqueta");
    assert.notStrictEqual(
        window.escaparHtml(encoded),
        encoded,
        "El helper codifica ampersands: sus resultados no deben escaparse dos veces"
    );
}

assert.strictEqual(window.escaparHtml(null), "");
assert.strictEqual(window.escaparHtml('"\'&'), "&quot;&#39;&amp;");
console.log("XSS escape tests passed: HTML metacharacters are encoded for HTML text/quoted attributes.");
