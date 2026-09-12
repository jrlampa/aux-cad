/**
 * vias_obstrucoes.js - Renderização de Vias, Calçadas (Passeios) e Obstruções Físicas
 * Consulta a API Overpass (OpenStreetMap) em tempo real com dados vetoriais reais e custo zero.
 */

const ViasObstrucoesState = {
    ativo: true,
    desenharNoCad: false,
    cacheGrid: new Set(), // Chaves "lat_lon" de quadrículas já carregadas
    camadaVias: null,
    camadaCalcadas: null,
    camadaObstrucoes: null,
    carregando: false
};

/**
 * Inicializa as camadas no mapa Leaflet
 */
function inicializarCamadasUrbanas(mapa) {
    if (!mapa) return;
    if (!ViasObstrucoesState.camadaVias) {
        ViasObstrucoesState.camadaVias = L.layerGroup().addTo(mapa);
    }
    if (!ViasObstrucoesState.camadaCalcadas) {
        ViasObstrucoesState.camadaCalcadas = L.layerGroup().addTo(mapa);
    }
    if (!ViasObstrucoesState.camadaObstrucoes) {
        ViasObstrucoesState.camadaObstrucoes = L.layerGroup().addTo(mapa);
    }
}

/**
 * Alterna a visibilidade das vias, calçadas e obstruções
 */
function toggleViasObstrucoes(mapa) {
    ViasObstrucoesState.ativo = !ViasObstrucoesState.ativo;
    const btn = document.getElementById('btnToggleVias');

    if (btn) {
        if (ViasObstrucoesState.ativo) {
            btn.classList.add('active');
            btn.innerHTML = '🏙️ Vias: VISÍVEIS';
        } else {
            btn.classList.remove('active');
            btn.innerHTML = '🏙️ Vias/Passeios';
        }
    }

    if (!mapa) return;
    inicializarCamadasUrbanas(mapa);

    if (ViasObstrucoesState.ativo) {
        if (!mapa.hasLayer(ViasObstrucoesState.camadaVias)) mapa.addLayer(ViasObstrucoesState.camadaVias);
        if (!mapa.hasLayer(ViasObstrucoesState.camadaCalcadas)) mapa.addLayer(ViasObstrucoesState.camadaCalcadas);
        if (!mapa.hasLayer(ViasObstrucoesState.camadaObstrucoes)) mapa.addLayer(ViasObstrucoesState.camadaObstrucoes);

        // Se houver posição atual, carrega o entorno
        if (window.AppState && window.AppState.currentLat) {
            carregarContextoUrbano(window.AppState.currentLat, window.AppState.currentLon, 120, mapa);
        }
    } else {
        if (mapa.hasLayer(ViasObstrucoesState.camadaVias)) mapa.removeLayer(ViasObstrucoesState.camadaVias);
        if (mapa.hasLayer(ViasObstrucoesState.camadaCalcadas)) mapa.removeLayer(ViasObstrucoesState.camadaCalcadas);
        if (mapa.hasLayer(ViasObstrucoesState.camadaObstrucoes)) mapa.removeLayer(ViasObstrucoesState.camadaObstrucoes);
    }
}

/**
 * Calcula a Bounding Box em torno de uma coordenada central
 */
function calcularBbox(lat, lon, raioMetros) {
    const deltaLat = raioMetros / 111111.0;
    const deltaLon = raioMetros / (111111.0 * Math.cos(lat * (Math.PI / 180.0)));
    return {
        south: lat - deltaLat,
        north: lat + deltaLat,
        west: lon - deltaLon,
        east: lon + deltaLon
    };
}

/**
 * Carrega vias, calçadas e edificações/obstruções da Overpass API
 */
async function carregarContextoUrbano(lat, lon, raioMetros = 100, mapa = null) {
    if (!ViasObstrucoesState.ativo) return;

    inicializarCamadasUrbanas(mapa);

    // Chave de quadrícula (~100m) para evitar consultas duplicadas
    const gridKey = `${lat.toFixed(3)}_${lon.toFixed(3)}`;
    if (ViasObstrucoesState.cacheGrid.has(gridKey)) {
        return; // Já consultado previamente
    }
    ViasObstrucoesState.cacheGrid.add(gridKey);

    const bbox = calcularBbox(lat, lon, raioMetros);
    const bboxStr = `${bbox.south.toFixed(5)},${bbox.west.toFixed(5)},${bbox.north.toFixed(5)},${bbox.east.toFixed(5)}`;

    const queryOverpass = `[out:json][timeout:15];(way["highway"](${bboxStr});way["building"](${bboxStr});way["barrier"](${bboxStr}););out body;>;out skel qt;`;
    const url = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(queryOverpass)}`;

    try {
        ViasObstrucoesState.carregando = true;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Status Overpass: ${res.status}`);
        const data = await res.json();
        renderizarElementosOsm(data, mapa);
    } catch (err) {
        // Fallback silencioso (permite operar offline ou em redes restritas sem travar)
        console.warn('[Vias/Obstruções OSM] Consulta externa:', err.message);
    } finally {
        ViasObstrucoesState.carregando = false;
    }
}

/**
 * Processa e renderiza os elementos do OpenStreetMap no mapa Leaflet
 */
function renderizarElementosOsm(osmData, mapa) {
    if (!osmData || !osmData.elements) return;

    // Indexa nós por ID
    const nodes = {};
    osmData.elements.forEach(el => {
        if (el.type === 'node') {
            nodes[el.id] = [el.lat, el.lon];
        }
    });

    const elementosCad = {
        vias: [],
        calcadas: [],
        obstrucoes: []
    };

    osmData.elements.forEach(el => {
        if (el.type !== 'way' || !el.nodes || el.nodes.length < 2) return;

        const coords = el.nodes.map(nodeId => nodes[nodeId]).filter(Boolean);
        if (coords.length < 2) return;

        const tags = el.tags || {};

        // 1. Edificações e Construções (Obstruções Físicas)
        if (tags.building) {
            const nomeEdif = tags.name || tags['addr:street'] || 'Edificação';
            const poly = L.polygon(coords, {
                color: '#64748b',
                weight: 1.5,
                fillColor: '#94a3b8',
                fillOpacity: 0.35
            }).bindTooltip(`<b>🏢 ${nomeEdif}</b><br>Obstrução / Edificação`, { sticky: true });

            ViasObstrucoesState.camadaObstrucoes.addLayer(poly);
            elementosCad.obstrucoes.push({ tipo: 'EDIFICACAO', nome: nomeEdif, coords });
        }
        // 2. Muros e Barreiras (Obstruções Lineares)
        else if (tags.barrier) {
            const barreiraLinha = L.polyline(coords, {
                color: '#dc2626', // Vermelho alerta
                weight: 2,
                dashArray: '3, 4',
                opacity: 0.8
            }).bindTooltip(`<b>🚧 Barreira / Muro</b> (${tags.barrier})`, { sticky: true });

            ViasObstrucoesState.camadaObstrucoes.addLayer(barreiraLinha);
            elementosCad.obstrucoes.push({ tipo: 'BARREIRA', nome: tags.barrier, coords });
        }
        // 3. Calçadas e Passeios Públicos
        else if (tags.footway === 'sidewalk' || tags.sidewalk || tags.highway === 'footway' || tags.highway === 'pedestrian') {
            const calcadaLinha = L.polyline(coords, {
                color: '#d97706', // Âmbar claro para passeio público
                weight: 2.5,
                dashArray: '2, 3',
                opacity: 0.85
            }).bindTooltip('<b>🚶 Calçada / Passeio Público</b>', { sticky: true });

            ViasObstrucoesState.camadaCalcadas.addLayer(calcadaLinha);
            elementosCad.calcadas.push({ tipo: 'PASSEIO', coords });
        }
        // 4. Vias e Ruas (Pistas de Rolamento / Eixos)
        else if (tags.highway) {
            const nomeRua = tags.name || tags['ref'] || 'Via Pública';
            const viaLinha = L.polyline(coords, {
                color: '#334155', // Asfalto escuro
                weight: 4.5,
                opacity: 0.75
            }).bindTooltip(`<b>🛣️ ${nomeRua}</b> (${tags.highway})`, { sticky: true });

            ViasObstrucoesState.camadaVias.addLayer(viaLinha);
            elementosCad.vias.push({ tipo: 'EIXO_VIA', nome: nomeRua, coords });
        }
    });

    // Se o envio ao CAD estiver ativado, notifica o C# via WebView2
    if (ViasObstrucoesState.desenharNoCad && window.chrome && window.chrome.webview) {
        converterEEnviarParaCad(elementosCad);
    }
}

/**
 * Converte coordenadas WGS84 para UTM e envia para o CAD via C#
 */
function converterEEnviarParaCad(elementos) {
    const fuso = (window.AppState && window.AppState.fusoUtm) ? window.AppState.fusoUtm : 23;
    if (!window.Snyder || typeof window.Snyder.latLonToUtm !== 'function') return;

    function converterLista(lista) {
        return lista.map(item => ({
            tipo: item.tipo,
            nome: item.nome || '',
            pontosUtm: item.coords.map(c => {
                const utm = window.Snyder.latLonToUtm(c[0], c[1], fuso);
                return [utm.x, utm.y];
            })
        }));
    }

    const payload = {
        action: 'desenhar_elementos_urbanos',
        fuso,
        vias: converterLista(elementos.vias),
        calcadas: converterLista(elementos.calcadas),
        obstrucoes: converterLista(elementos.obstrucoes)
    };

    window.chrome.webview.postMessage(payload);
}

// Exporta para o escopo global
window.ViasObstrucoesState = ViasObstrucoesState;
window.toggleViasObstrucoes = toggleViasObstrucoes;
window.carregarContextoUrbano = carregarContextoUrbano;
window.calcularBbox = calcularBbox;
window.renderizarElementosOsm = renderizarElementosOsm;
