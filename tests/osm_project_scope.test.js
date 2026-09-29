const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const sourcePath = path.join(__dirname, '..', 'mapa_cad_paleta', 'web', 'vias_obstrucoes.js');
const source = fs.readFileSync(sourcePath, 'utf8');

function createHarness() {
    const pendingRequests = [];
    const renderCalls = [];
    const postedMessages = [];
    const sandbox = {
        AbortSignal: { timeout: () => ({}) },
        clearTimeout,
        console: new Proxy({}, { get: () => () => {} }),
        document: {
            readyState: 'complete',
            getElementById: () => null
        },
        fetch: (url, options) => new Promise((resolve, reject) => {
            pendingRequests.push({ url, options, resolve, reject });
        }),
        localStorage: { getItem: () => null, setItem: () => {} },
        performance: { now: () => 0 },
        setTimeout,
        window: {
            AppState: { currentLat: -23.5, currentLon: -46.6 },
            Snyder: { latLonToUtm: (lat, lon) => ({ x: lon, y: lat }) },
            chrome: { webview: { postMessage: message => postedMessages.push(message) } }
        }
    };

    vm.createContext(sandbox);
    vm.runInContext(source, sandbox, { filename: sourcePath });
    sandbox.renderizarElementosOsm = (...args) => renderCalls.push(args);

    return { pendingRequests, postedMessages, renderCalls, sandbox };
}

function bind(harness, sobId, generation) {
    return harness.sandbox.window.aplicarProjectScopeOsm({
        status: 'Bound',
        sobId,
        generation
    });
}

function response(status, data) {
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: { get: () => null },
        text: async () => JSON.stringify(data)
    };
}

function osmResult() {
    return {
        elements: [{
            type: 'way',
            id: 77,
            tags: { highway: 'residential', name: 'Rua de teste' },
            geometry: [{ lat: -23.5, lon: -46.6 }, { lat: -23.501, lon: -46.601 }]
        }]
    };
}

test('T01: consulta OSM não inicia sem ProjectScope vinculado', async () => {
    const harness = createHarness();

    await harness.sandbox.window.carregarContextoUrbano(-23.5, -46.6);

    assert.equal(harness.pendingRequests.length, 0);
    assert.equal(harness.sandbox.window.ViasObstrucoesState.carregando, false);
});

test('T02: nova geração vincula o escopo e limpa o estado transitório anterior', () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    let clearedLayers = 0;
    state.camadaVias = { clearLayers: () => clearedLayers++ };
    state.camadaCalcadas = { clearLayers: () => clearedLayers++ };
    state.camadaObstrucoes = { clearLayers: () => clearedLayers++ };
    assert.equal(bind(harness, 'PROJETO-A', 1), true);
    clearedLayers = 0;
    state.cacheGrid.add('grid');
    state.waysProcessados.add(77);
    state.elementosAcumulados.vias.push({ osmId: 77 });
    state.ultimaFalha = { status: 'HTTP_ERROR' };

    assert.equal(bind(harness, 'PROJETO-B', 2), true);
    assert.equal(state.projectScope, 'PROJETO-B');
    assert.equal(state.projectGeneration, 2);
    assert.equal(state.cacheGrid.size, 0);
    assert.equal(state.waysProcessados.size, 0);
    assert.equal(state.elementosAcumulados.vias.length, 0);
    assert.equal(state.ultimaFalha, null);
    assert.equal(clearedLayers, 3);
});

test('T03: repetição idempotente da geração atual preserva o estado do escopo', () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    assert.equal(bind(harness, 'PROJETO-A', 3), true);
    state.cacheGrid.add('grid');
    state.waysProcessados.add(77);
    state.elementosAcumulados.vias.push({ osmId: 77 });

    assert.equal(bind(harness, 'PROJETO-A', 3), true);
    assert.equal(state.cacheGrid.has('grid'), true);
    assert.equal(state.waysProcessados.has(77), true);
    assert.equal(state.elementosAcumulados.vias.length, 1);
});

test('T04: notificação antiga não reverte o ProjectScope atual', () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    assert.equal(bind(harness, 'PROJETO-B', 4), true);
    state.cacheGrid.add('grid-b');

    assert.equal(harness.sandbox.window.handleProjectScopeChanged({
        status: 'Bound',
        sobId: 'PROJETO-A',
        generation: 3
    }), false);
    assert.equal(state.projectScope, 'PROJETO-B');
    assert.equal(state.projectGeneration, 4);
    assert.equal(state.cacheGrid.has('grid-b'), true);
});

test('T05: resposta tardia de carregarContextoUrbano não altera nem renderiza o escopo novo', async () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    assert.equal(bind(harness, 'PROJETO-A', 5), true);

    const operation = harness.sandbox.window.carregarContextoUrbano(-23.5, -46.6, 150, null, true);
    assert.equal(harness.pendingRequests.length, 1);
    assert.equal(bind(harness, 'PROJETO-B', 6), true);
    harness.pendingRequests[0].resolve(response(200, osmResult()));
    await operation;

    assert.equal(harness.renderCalls.length, 0);
    assert.equal(state.cacheGrid.size, 0);
    assert.equal(state.carregando, false);
});

test('T06: resposta tardia de desenho CAD é descartada mesmo se a identidade do projeto não mudou', async () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    assert.equal(bind(harness, 'PROJETO-A', 7), true);

    const operation = harness.sandbox.window.desenharViasNoCad(true);
    assert.equal(harness.pendingRequests.length, 1);
    assert.equal(bind(harness, 'PROJETO-A', 8), true);
    harness.pendingRequests[0].resolve(response(200, osmResult()));
    await operation;

    assert.equal(harness.renderCalls.length, 0);
    assert.equal(harness.postedMessages.length, 0);
    assert.equal(state.elementosAcumulados.vias.length, 0);
});

test('T07: erro tardio não sobrescreve o estado de falha do escopo novo', async () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    assert.equal(bind(harness, 'PROJETO-A', 9), true);

    const operation = harness.sandbox.window.carregarContextoUrbano(-23.5, -46.6, 150, null, true);
    assert.equal(harness.pendingRequests.length, 1);
    assert.equal(bind(harness, 'PROJETO-B', 10), true);
    const currentFailure = { status: 'CURRENT_PROJECT_FAILURE' };
    state.ultimaFalha = currentFailure;
    harness.pendingRequests[0].resolve(response(400, {}));
    await operation;

    assert.equal(state.ultimaFalha, currentFailure);
    assert.equal(harness.renderCalls.length, 0);
});

test('T08: o mesmo elemento OSM pode ser processado separadamente em outro projeto', () => {
    const harness = createHarness();
    const state = harness.sandbox.window.ViasObstrucoesState;
    const renderizar = harness.sandbox.window.renderizarElementosOsm;

    assert.equal(bind(harness, 'PROJETO-A', 11), true);
    renderizar(osmResult(), null, false);
    assert.equal(state.elementosAcumulados.vias.length, 1);
    assert.equal(state.waysProcessados.has(77), true);

    assert.equal(bind(harness, 'PROJETO-B', 12), true);
    renderizar(osmResult(), null, false);
    assert.equal(state.projectScope, 'PROJETO-B');
    assert.equal(state.elementosAcumulados.vias.length, 1);
    assert.equal(state.waysProcessados.has(77), true);
});
