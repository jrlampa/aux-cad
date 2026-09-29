/**
 * vias_obstrucoes.js - Renderização de Vias, Calçadas (Passeios) e Obstruções Físicas
 * Consulta a API Overpass (OpenStreetMap) em tempo real com dados vetoriais reais e custo zero.
 * Desenha automaticamente no Leaflet e no AutoCAD (layers VIAS_EIXO, VIAS_CALCADA e OBSTRUCOES_EDIF).
 */

const ViasObstrucoesState = {
    ativo: true,
    desenharNoCad: true, // Envio automático ao AutoCAD habilitado por padrão
    cacheGrid: new Set(), // Chaves "lat_lon" de quadrículas já carregadas
    waysProcessados: new Set(), // IDs de 'way' já renderizados/enviados (evita duplicações)
    elementosAcumulados: {
        vias: [],
        calcadas: [],
        obstrucoes: []
    },
    camadaVias: null,
    camadaCalcadas: null,
    camadaObstrucoes: null,
    carregando: false,
    inFlightRequests: new Map(),
    ultimaFalha: null,
    projectScope: null,
    projectGeneration: -1
};

function limparElementosOsmAcumulados() {
    ViasObstrucoesState.elementosAcumulados.vias.length = 0;
    ViasObstrucoesState.elementosAcumulados.calcadas.length = 0;
    ViasObstrucoesState.elementosAcumulados.obstrucoes.length = 0;

    for (const layer of [
        ViasObstrucoesState.camadaVias,
        ViasObstrucoesState.camadaCalcadas,
        ViasObstrucoesState.camadaObstrucoes
    ]) {
        if (layer) layer.clearLayers();
    }
}

function capturarContextoOsm() {
    const { projectScope, projectGeneration } = ViasObstrucoesState;
    if (!projectScope || !Number.isSafeInteger(projectGeneration) || projectGeneration < 0) return null;
    return { sobId: projectScope, generation: projectGeneration };
}

function contextoOsmAindaAtual(contexto) {
    return !!contexto
        && ViasObstrucoesState.projectScope === contexto.sobId
        && ViasObstrucoesState.projectGeneration === contexto.generation;
}

function invalidarEstadoOsmPorProjectScope(scope) {
    const generation = Number(scope?.generation);
    if (!Number.isSafeInteger(generation) || generation < 0) return false;

    const sobId = typeof scope.sobId === 'string' ? scope.sobId.trim().toUpperCase() : '';
    const bound = scope.status === 'Bound' && !!sobId;
    const nextProjectScope = bound ? sobId : null;
    if (generation < ViasObstrucoesState.projectGeneration) return false;
    if (generation === ViasObstrucoesState.projectGeneration) {
        return ViasObstrucoesState.projectScope === nextProjectScope;
    }

    ViasObstrucoesState.projectGeneration = generation;
    ViasObstrucoesState.projectScope = nextProjectScope;
    ViasObstrucoesState.cacheGrid.clear();
    ViasObstrucoesState.waysProcessados.clear();
    limparElementosOsmAcumulados();
    ViasObstrucoesState.inFlightRequests.clear();
    ViasObstrucoesState.carregando = false;
    ViasObstrucoesState.ultimaFalha = null;

    return true;
}

/**
 * Sincroniza a opção de gerar vias automaticamente no AutoCAD conforme novos postes são inseridos
 */
function sincronizarOpcaoViasCad(ativo) {
    ViasObstrucoesState.desenharNoCad = !!ativo;

    const chkAuto = document.getElementById('chkAutoViasCad');
    if (chkAuto && chkAuto.checked !== ViasObstrucoesState.desenharNoCad) {
        chkAuto.checked = ViasObstrucoesState.desenharNoCad;
    }

    const chkTracado = document.getElementById('chkTracadoViasCad');
    if (chkTracado && chkTracado.checked !== ViasObstrucoesState.desenharNoCad) {
        chkTracado.checked = ViasObstrucoesState.desenharNoCad;
    }

    try {
        localStorage.setItem('AUXCAD_AUTO_VIAS_CAD', ViasObstrucoesState.desenharNoCad ? 'true' : 'false');
    } catch (e) {
        console.warn('Falha ao persistir AUXCAD_AUTO_VIAS_CAD:', e);
    }

    if (typeof showToast === 'function') {
        if (ViasObstrucoesState.desenharNoCad) {
            showToast('🛣️ Gerar vias no AutoCAD ao inserir postes: ATIVADO', 'info');
        } else {
            showToast('🛣️ Gerar vias no AutoCAD ao inserir postes: DESATIVADO', 'info');
        }
    }
}

/**
 * Inicializa a opção de gerar vias do localStorage
 */
function inicializarOpcaoViasCad() {
    let ativo = true;
    try {
        const val = localStorage.getItem('AUXCAD_AUTO_VIAS_CAD');
        if (val !== null) ativo = (val === 'true');
    } catch (e) {}

    ViasObstrucoesState.desenharNoCad = ativo;
    const chkAuto = document.getElementById('chkAutoViasCad');
    if (chkAuto) chkAuto.checked = ativo;
    const chkTracado = document.getElementById('chkTracadoViasCad');
    if (chkTracado) chkTracado.checked = ativo;
}

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
 * Alterna a visibilidade e envio das vias, calçadas e obstruções
 */
function toggleViasObstrucoes(mapa) {
    ViasObstrucoesState.ativo = !ViasObstrucoesState.ativo;
    const btn = document.getElementById('btnToggleVias');

    if (btn) {
        if (ViasObstrucoesState.ativo) {
            btn.classList.add('active');
            btn.innerHTML = '🏙️ Vias: VISÍVEIS';
            if (typeof showToast === 'function') {
                showToast('🏙️ Camadas de vias ativadas no mapa', 'info');
            }
        } else {
            btn.classList.remove('active');
            btn.innerHTML = '🏙️ Vias/Passeios';
            if (typeof showToast === 'function') {
                showToast('🏙️ Camadas de vias ocultadas no mapa (CAD continua ativo)', 'info');
            }
        }
    }

    if (!mapa) return;
    inicializarCamadasUrbanas(mapa);

    if (ViasObstrucoesState.ativo) {
        if (!mapa.hasLayer(ViasObstrucoesState.camadaVias)) mapa.addLayer(ViasObstrucoesState.camadaVias);
        if (!mapa.hasLayer(ViasObstrucoesState.camadaCalcadas)) mapa.addLayer(ViasObstrucoesState.camadaCalcadas);
        if (!mapa.hasLayer(ViasObstrucoesState.camadaObstrucoes)) mapa.addLayer(ViasObstrucoesState.camadaObstrucoes);

        desenharViasNoCad(false, mapa);
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
 * Converte XML retornado pela API OSM 0.6 para a estrutura padrão de elementos JSON
 */
function converterOsmXmlParaJson(xmlDoc) {
    const elements = [];
    const nodeElements = xmlDoc.getElementsByTagName('node');
    for (let i = 0; i < nodeElements.length; i++) {
        const n = nodeElements[i];
        elements.push({
            type: 'node',
            id: parseInt(n.getAttribute('id') || '0', 10),
            lat: parseFloat(n.getAttribute('lat') || '0'),
            lon: parseFloat(n.getAttribute('lon') || '0')
        });
    }

    const wayElements = xmlDoc.getElementsByTagName('way');
    for (let i = 0; i < wayElements.length; i++) {
        const w = wayElements[i];
        const id = parseInt(w.getAttribute('id') || '0', 10);
        const nodes = [];
        const ndList = w.getElementsByTagName('nd');
        for (let j = 0; j < ndList.length; j++) {
            nodes.push(parseInt(ndList[j].getAttribute('ref') || '0', 10));
        }

        const tags = {};
        const tagList = w.getElementsByTagName('tag');
        for (let j = 0; j < tagList.length; j++) {
            tags[tagList[j].getAttribute('k')] = tagList[j].getAttribute('v');
        }

        elements.push({
            type: 'way',
            id,
            nodes,
            tags
        });
    }

    return { elements };
}

/**
 * Executa consulta de vias, passeios e obstruções com prioridade máxima para a API Oficial OSM
 * Zero bloqueio CORS (Access-Control-Allow-Origin: *), tempo de resposta inferior a 1s
 */
function obterChaveConsultaOsm(bbox) {
    return `vias-v1:${bbox.south.toFixed(6)},${bbox.west.toFixed(6)},${bbox.north.toFixed(6)},${bbox.east.toFixed(6)}`;
}

function aguardarOsm(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function obterRetryAfterMs(res) {
    const valor = res.headers?.get('Retry-After');
    if (!valor) return null;
    const segundos = Number(valor);
    if (Number.isFinite(segundos)) return Math.max(0, segundos * 1000);
    const data = Date.parse(valor);
    return Number.isFinite(data) ? Math.max(0, data - Date.now()) : null;
}

function resultadoOsm(status, detalhes = {}) {
    return { status, data: detalhes.data || null, ...detalhes };
}

async function executarConsultaOsmInterna(bbox, requestKey) {
    const inicio = performance.now();
    const urlOsm = `https://api.openstreetmap.org/api/0.6/map.json?bbox=${bbox.west.toFixed(6)},${bbox.south.toFixed(6)},${bbox.east.toFixed(6)},${bbox.north.toFixed(6)}`;
    let ultimaFalha = null;
    const maxTentativasOficial = 2;

    for (let tentativa = 1; tentativa <= maxTentativasOficial; tentativa++) {
        try {
            console.info('[OSMPALETA][OSM][REQUEST]', { endpoint: urlOsm, bbox, requestKey, tentativa });
            const res = await fetch(urlOsm, {
                method: 'GET',
                headers: { 'Accept': 'application/json, application/xml, text/xml, */*' },
                signal: AbortSignal.timeout(8000)
            });
            const elapsedMs = Math.round(performance.now() - inicio);
            console.info('[OSMPALETA][OSM][RESPONSE]', { status: res.status, elapsedMs, endpoint: urlOsm });

            if (res.status === 429) {
                const retryAfterMs = obterRetryAfterMs(res);
                console.warn('[OSMPALETA][OSM][429]', { status: res.status, retryAfter: retryAfterMs, tentativa, endpoint: urlOsm });
                if (tentativa < maxTentativasOficial) {
                    if (retryAfterMs !== null && retryAfterMs > 10000) {
                        return resultadoOsm('RATE_LIMITED', { endpoint: urlOsm, attempts: tentativa, elapsedMs, retryAfterMs });
                    }
                    const delayMs = retryAfterMs ?? 2000;
                    console.info('[OSMPALETA][OSM][RETRY]', { attempt: tentativa + 1, delayMs });
                    await aguardarOsm(delayMs);
                    continue;
                }
                return resultadoOsm('RATE_LIMITED', { endpoint: urlOsm, attempts: tentativa, elapsedMs, retryAfterMs });
            }

            if (!res.ok) {
                ultimaFalha = resultadoOsm(res.status >= 500 ? 'SERVER_ERROR' : 'HTTP_ERROR', { endpoint: urlOsm, attempts: tentativa, elapsedMs, httpStatus: res.status });
                break;
            }

            const rawText = (await res.text()).trim();
            if (!rawText) return resultadoOsm('EMPTY_RESULT', { endpoint: urlOsm, attempts: tentativa, elapsedMs });
            let data;
            if (rawText.startsWith('<')) {
                const xmlDoc = new DOMParser().parseFromString(rawText, 'text/xml');
                data = converterOsmXmlParaJson(xmlDoc);
            } else {
                data = JSON.parse(rawText);
            }
            if (!data || !Array.isArray(data.elements)) return resultadoOsm('INVALID_RESPONSE', { endpoint: urlOsm, attempts: tentativa, elapsedMs });
            if (data.elements.length === 0) return resultadoOsm('EMPTY_RESULT', { endpoint: urlOsm, attempts: tentativa, elapsedMs });
            console.info('[OSMPALETA][OSM][FINAL]', { status: 'SUCCESS', endpoint: urlOsm, attempts: tentativa, elapsedMs });
            return resultadoOsm('SUCCESS', { data, endpoint: urlOsm, attempts: tentativa, elapsedMs });
        } catch (err) {
            const elapsedMs = Math.round(performance.now() - inicio);
            const status = err?.name === 'TimeoutError' || err?.name === 'AbortError' ? 'TIMEOUT' : 'NETWORK_ERROR';
            ultimaFalha = resultadoOsm(status, { endpoint: urlOsm, attempts: tentativa, elapsedMs, error: err });
            console.warn('[OSMPALETA][OSM][ERRO]', { status, endpoint: urlOsm, attempts: tentativa, elapsedMs });
            break;
        }
    }

    // Fallback somente para falhas transitórias; 429 não gera rajada em outros provedores.
    if (!ultimaFalha || !['TIMEOUT', 'NETWORK_ERROR', 'SERVER_ERROR'].includes(ultimaFalha.status)) {
        console.warn('[OSMPALETA][OSM][FINAL]', ultimaFalha || resultadoOsm('HTTP_ERROR', { endpoint: urlOsm }));
        return ultimaFalha || resultadoOsm('HTTP_ERROR', { endpoint: urlOsm });
    }

    const bboxStr = `${bbox.south.toFixed(5)},${bbox.west.toFixed(5)},${bbox.north.toFixed(5)},${bbox.east.toFixed(5)}`;
    const queryOverpass = `[out:json][timeout:15];(way["highway"](${bboxStr});way["building"](${bboxStr});way["barrier"](${bboxStr}););out body geom;>;out skel qt;`;
    const bodyData = 'data=' + encodeURIComponent(queryOverpass);
    const fallbackEndpoints = [
        'https://overpass.private.coffee/api/interpreter',
        'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
    ];
    let fallbackRateLimited = false;

    for (const endpoint of fallbackEndpoints) {
        try {
            console.info('[OSMPALETA][OSM][REQUEST]', { endpoint, bbox, requestKey });
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Accept': 'application/json'
                },
                body: bodyData,
                signal: AbortSignal.timeout(12000)
            });
            const elapsedMs = Math.round(performance.now() - inicio);
            console.info('[OSMPALETA][OSM][RESPONSE]', { status: res.status, elapsedMs, endpoint });
            if (res.status === 429) {
                fallbackRateLimited = true;
                console.warn('[OSMPALETA][OSM][429]', { status: res.status, retryAfter: obterRetryAfterMs(res), tentativa: 1, endpoint });
                continue;
            }
            if (!res.ok) continue;
            const data = await res.json();
            if (data && Array.isArray(data.elements) && data.elements.length > 0) {
                console.info('[OSMPALETA][OSM][FINAL]', { status: 'SUCCESS', endpoint, attempts: 1, elapsedMs });
                return resultadoOsm('SUCCESS', { data, endpoint, attempts: 1, elapsedMs });
            }
        } catch (err) {
            console.warn('[OSMPALETA][OSM][ERRO]', { status: err?.name === 'TimeoutError' ? 'TIMEOUT' : 'NETWORK_ERROR', endpoint });
        }
    }

    return resultadoOsm(fallbackRateLimited ? 'RATE_LIMITED' : 'NETWORK_ERROR', {
        endpoint: ultimaFalha.endpoint,
        attempts: ultimaFalha.attempts,
        elapsedMs: Math.round(performance.now() - inicio)
    });
}

async function executarConsultaOsm(bbox) {
    if (!bbox) return resultadoOsm('INVALID_REQUEST');
    const requestKey = `${ViasObstrucoesState.projectGeneration}:${obterChaveConsultaOsm(bbox)}`;
    const existente = ViasObstrucoesState.inFlightRequests.get(requestKey);
    if (existente) {
        console.info('[OSMPALETA][OSM][DEDUP] requisição já em andamento', requestKey);
        console.info('[OSMPALETA][OSM][DEDUP] resultado compartilhado', requestKey);
        return existente;
    }

    console.info('[OSMPALETA][OSM][DEDUP] nova requisição', requestKey);
    const requisicao = executarConsultaOsmInterna(bbox, requestKey).finally(() => {
        ViasObstrucoesState.inFlightRequests.delete(requestKey);
    });
    ViasObstrucoesState.inFlightRequests.set(requestKey, requisicao);
    return requisicao;
}

/**
 * Carrega vias, calçadas e edificações/obstruções da OpenStreetMap API
 */
async function carregarContextoUrbano(lat, lon, raioMetros = 150, mapa = null, forcarCad = false) {
    const contexto = capturarContextoOsm();
    if (!contexto) return;
    const querCad = forcarCad || ViasObstrucoesState.desenharNoCad;
    if (!ViasObstrucoesState.ativo && !querCad) return;

    if (mapa && ViasObstrucoesState.ativo) {
        inicializarCamadasUrbanas(mapa);
    }

    // Chave de quadrícula (~100m) para evitar consultas redundantes
    const gridKey = `${lat.toFixed(3)}_${lon.toFixed(3)}`;
    if (ViasObstrucoesState.cacheGrid.has(gridKey)) {
        // Se já consultou e temos elementos acumulados, garante envio ao CAD
        if (querCad && window.chrome && window.chrome.webview) {
            converterEEnviarParaCad(ViasObstrucoesState.elementosAcumulados);
        }
        return;
    }

    const bbox = calcularBbox(lat, lon, raioMetros);

    ViasObstrucoesState.carregando = true;
    const resultado = await executarConsultaOsm(bbox);
    if (!contextoOsmAindaAtual(contexto)) return;
    ViasObstrucoesState.carregando = false;

    if (resultado.status === 'SUCCESS' && resultado.data) {
        ViasObstrucoesState.cacheGrid.add(gridKey);
        renderizarElementosOsm(resultado.data, ViasObstrucoesState.ativo ? mapa : null, querCad);
    } else {
        ViasObstrucoesState.ultimaFalha = resultado;
        console.warn('[OSMPALETA][OSM][ERRO]', { ...resultado, bbox });
        if (typeof showToast === 'function') {
            showToast(resultado.status === 'RATE_LIMITED'
                ? 'O OpenStreetMap limitou temporariamente as consultas. Aguarde alguns segundos e tente novamente.'
                : 'Não foi possível consultar os dados do OpenStreetMap neste momento.', 'warning');
        }
    }
}

/**
 * Força o desenho das vias e passeios no AutoCAD cobrindo a área da rede/mapa
 */
async function desenharViasNoCad(forcarReconsulta = false, mapa = null) {
    const contexto = capturarContextoOsm();
    if (!contexto) {
        if (typeof showToast === 'function') {
            showToast('O projeto ativo ainda não possui ProjectScope vinculado.', 'warning');
        }
        return;
    }

    const map = mapa || (window.AppState ? window.AppState.map : null);
    
    // Se já temos elementos carregados e não foi forçada reconsulta completa:
    if (!forcarReconsulta && ViasObstrucoesState.elementosAcumulados.vias.length > 0) {
        converterEEnviarParaCad(ViasObstrucoesState.elementosAcumulados);
        if (typeof showToast === 'function') {
            showToast(`🛣️ ${ViasObstrucoesState.elementosAcumulados.vias.length} vias enviadas para desenho no AutoCAD!`, 'success');
        }
        return;
    }

    if (typeof showToast === 'function') {
        showToast('🛣️ Localizando e desenhando vias no AutoCAD...', 'info');
    }

    // Calcula Bbox envolvendo todos os postes do traçado
    let bbox = null;
    const pontosTracado = (window.TracadoState && window.TracadoState.pontos) ? window.TracadoState.pontos : [];

    if (pontosTracado.length > 0) {
        let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
        let count = 0;
        for (const p of pontosTracado) {
            if (p.lat && p.lon) {
                minLat = Math.min(minLat, p.lat);
                maxLat = Math.max(maxLat, p.lat);
                minLon = Math.min(minLon, p.lon);
                maxLon = Math.max(maxLon, p.lon);
                count++;
            }
        }
        if (count > 0) {
            const margem = 0.0018; // ~200 metros de margem
            bbox = {
                south: minLat - margem,
                west: minLon - margem,
                north: maxLat + margem,
                east: maxLon + margem
            };
        }
    }

    // Fallback: usar viewport visível do mapa ou coordenada central
    if (!bbox && map) {
        const bounds = map.getBounds();
        bbox = {
            south: bounds.getSouth(),
            west: bounds.getWest(),
            north: bounds.getNorth(),
            east: bounds.getEast()
        };
    } else if (!bbox && window.AppState && window.AppState.currentLat) {
        bbox = calcularBbox(window.AppState.currentLat, window.AppState.currentLon, 250);
    }

    if (!bbox) {
        if (typeof showToast === 'function') {
            showToast('Posicione o mapa ou trace um poste para localizar as vias.', 'warning');
        }
        return;
    }

    const resultado = await executarConsultaOsm(bbox);
    if (!contextoOsmAindaAtual(contexto)) return;

    if (resultado.status === 'SUCCESS' && resultado.data) {
        if (forcarReconsulta) {
            ViasObstrucoesState.cacheGrid.clear();
            ViasObstrucoesState.waysProcessados.clear();
            limparElementosOsmAcumulados();
        }
        renderizarElementosOsm(resultado.data, map, true);
        const nVias = ViasObstrucoesState.elementosAcumulados.vias.length;
        if (typeof showToast === 'function') {
            showToast(`🛣️ ${nVias} trechos de vias/passeios desenhados no CAD!`, 'success');
        }
    } else {
        console.warn('[OSMPALETA][OSM][ERRO]', { ...resultado, bbox });
        if (typeof showToast === 'function') {
            showToast(resultado.status === 'RATE_LIMITED'
                ? 'O OpenStreetMap limitou temporariamente as consultas. Aguarde alguns segundos e tente novamente.'
                : 'Não foi possível obter os eixos de vias do OSM no momento.', 'warning');
        }
    }
}

/**
 * Processa e renderiza os elementos do OpenStreetMap no mapa Leaflet
 */
function renderizarElementosOsm(osmData, mapa, enviarCad = false) {
    if (!osmData || !osmData.elements) return;

    const pipeline = {
        elementosOsmRecebidos: osmData.elements.length,
        waysEncontradas: 0,
        waysComHighway: 0,
        waysComNodes: 0,
        waysComCoords: 0,
        waysConvertidasUtm: 0,
        viasPayload: 0,
        calcadasPayload: 0,
        obstrucoesPayload: 0,
        totalVerticesPayload: 0,
        descartes: {}
    };

    // Indexa nós por ID
    const nodes = {};
    osmData.elements.forEach(el => {
        if (el.type === 'node') {
            nodes[el.id] = [el.lat, el.lon];
        }
    });

    const novosElementos = {
        vias: [],
        calcadas: [],
        obstrucoes: []
    };

    osmData.elements.forEach(el => {
        if (el.type !== 'way') return;

        pipeline.waysEncontradas += 1;
        const tags = el.tags || {};
        const highway = tags.highway || null;

        if (el.id && ViasObstrucoesState.waysProcessados.has(el.id)) {
            pipeline.descartes[el.id] = 'way já processado';
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tags,
                highway,
                nodes: Array.isArray(el.nodes) ? el.nodes.length : 0,
                coords: 0,
                pontosUtm: 0,
                status: 'DESCARTADO',
                motivo: 'way já processado'
            });
            return;
        }
        if (el.id) ViasObstrucoesState.waysProcessados.add(el.id);

        let coords = [];
        if (el.geometry && Array.isArray(el.geometry)) {
            coords = el.geometry.map(g => [g.lat, g.lon]);
        } else if (el.nodes && Array.isArray(el.nodes)) {
            coords = el.nodes.map(nodeId => nodes[nodeId]).filter(Boolean);
        }

        const nodesCount = Array.isArray(el.nodes) ? el.nodes.length : 0;
        const coordsCount = coords.length;

        if (highway) pipeline.waysComHighway += 1;
        if (nodesCount > 0) pipeline.waysComNodes += 1;
        if (coordsCount >= 2) pipeline.waysComCoords += 1;

        if (!highway && !tags.building && !tags.barrier && !(tags.footway === 'sidewalk' || tags.sidewalk || tags.highway === 'footway' || tags.highway === 'pedestrian')) {
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tags,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'DESCARTADO',
                motivo: 'sem tags relevantes (highway/building/barrier/footway)'
            });
            return;
        }

        if (coordsCount < 2) {
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tags,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'DESCARTADO',
                motivo: 'coords.length < 2'
            });
            return;
        }

        const tagsResumo = {
            building: !!tags.building,
            barrier: !!tags.barrier,
            footway: tags.footway || null,
            sidewalk: tags.sidewalk || null,
            highway: tags.highway || null
        };

        // 1. Edificações e Construções (Obstruções Físicas)
        if (tags.building) {
            const nomeEdif = tags.name || tags['addr:street'] || 'Edificação';
            if (mapa && ViasObstrucoesState.camadaObstrucoes) {
                const poly = L.polygon(coords, {
                    color: '#64748b',
                    weight: 1.5,
                    fillColor: '#94a3b8',
                    fillOpacity: 0.35
                }).bindTooltip(`<b>🏢 ${nomeEdif}</b><br>Obstrução / Edificação`, { sticky: true });

                ViasObstrucoesState.camadaObstrucoes.addLayer(poly);
            }
            novosElementos.obstrucoes.push({ osmId: el.id, osmType: el.type, tipo: 'EDIFICACAO', nome: nomeEdif, coords });
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tagsResumo,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'ACEITO',
                motivo: 'obstrução / building'
            });
        }
        // 2. Muros e Barreiras (Obstruções Lineares)
        else if (tags.barrier) {
            if (mapa && ViasObstrucoesState.camadaObstrucoes) {
                const barreiraLinha = L.polyline(coords, {
                    color: '#dc2626',
                    weight: 2,
                    dashArray: '3, 4',
                    opacity: 0.8
                }).bindTooltip(`<b>🚧 Barreira / Muro</b> (${tags.barrier})`, { sticky: true });

                ViasObstrucoesState.camadaObstrucoes.addLayer(barreiraLinha);
            }
            novosElementos.obstrucoes.push({ osmId: el.id, osmType: el.type, tipo: 'BARREIRA', nome: tags.barrier, coords });
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tagsResumo,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'ACEITO',
                motivo: 'obstrução / barrier'
            });
        }
        // 3. Calçadas e Passeios Públicos
        else if (tags.footway === 'sidewalk' || tags.sidewalk || tags.highway === 'footway' || tags.highway === 'pedestrian') {
            if (mapa && ViasObstrucoesState.camadaCalcadas) {
                const calcadaLinha = L.polyline(coords, {
                    color: '#d97706',
                    weight: 2.5,
                    dashArray: '2, 3',
                    opacity: 0.85
                }).bindTooltip('<b>🚶 Calçada / Passeio Público</b>', { sticky: true });

                ViasObstrucoesState.camadaCalcadas.addLayer(calcadaLinha);
            }
            novosElementos.calcadas.push({ osmId: el.id, osmType: el.type, tipo: 'PASSEIO', coords });
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tagsResumo,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'ACEITO',
                motivo: 'calcada / sidewalk / footway'
            });
        }
        // 4. Vias e Ruas (Pistas de Rolamento / Eixos)
        else if (tags.highway) {
            const nomeRua = tags.name || tags['ref'] || 'Via Pública';
            const { larguraPista, larguraCalcada } = calcularLargurasVia(tags);

            if (mapa && ViasObstrucoesState.camadaVias) {
                const viaLinha = L.polyline(coords, {
                    color: '#334155',
                    weight: Math.min(8, Math.max(3, larguraPista * 0.8)),
                    opacity: 0.75
                }).bindTooltip(`<b>🛣️ ${nomeRua}</b> (${tags.highway} - Pista: ${larguraPista.toFixed(1)}m, Passeio: ${larguraCalcada.toFixed(1)}m)`, { sticky: true });

                ViasObstrucoesState.camadaVias.addLayer(viaLinha);
            }
            novosElementos.vias.push({ 
                osmId: el.id,
                osmType: el.type,
                tipo: 'EIXO_VIA', 
                nome: nomeRua, 
                coords, 
                larguraPista, 
                larguraCalcada 
            });
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tagsResumo,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'ACEITO',
                motivo: 'via / highway'
            });
        } else {
            console.log('[OSMPALETA][OSM][WAY]', {
                id: el.id,
                type: el.type,
                tags: tagsResumo,
                highway,
                nodes: nodesCount,
                coords: coordsCount,
                pontosUtm: 0,
                status: 'DESCARTADO',
                motivo: 'condição não mapeada'
            });
        }
    });

    const totalNulosUtm = novosElementos.vias.length + novosElementos.calcadas.length + novosElementos.obstrucoes.length;
    pipeline.viasPayload = novosElementos.vias.length;
    pipeline.calcadasPayload = novosElementos.calcadas.length;
    pipeline.obstrucoesPayload = novosElementos.obstrucoes.length;
    pipeline.totalVerticesPayload = novosElementos.vias.reduce((sum, item) => sum + (item.coords ? item.coords.length : 0), 0)
        + novosElementos.calcadas.reduce((sum, item) => sum + (item.coords ? item.coords.length : 0), 0)
        + novosElementos.obstrucoes.reduce((sum, item) => sum + (item.coords ? item.coords.length : 0), 0);

    console.log('[OSMPALETA][PIPELINE]', pipeline);

    // Acumula elementos no estado global
    ViasObstrucoesState.elementosAcumulados.vias.push(...novosElementos.vias);
    ViasObstrucoesState.elementosAcumulados.calcadas.push(...novosElementos.calcadas);
    ViasObstrucoesState.elementosAcumulados.obstrucoes.push(...novosElementos.obstrucoes);

    // Se o envio ao CAD estiver ativado ou forçado pelo lançamento de poste
    const deveEnviarCad = enviarCad || ViasObstrucoesState.desenharNoCad;
    if (deveEnviarCad && window.chrome && window.chrome.webview) {
        converterEEnviarParaCad(novosElementos);
    }
}

/**
 * Calcula a largura da pista e do passeio a partir das tags do OSM
 */
function calcularLargurasVia(tags) {
    let larguraPista = 7.0; // Padrão urbano residencial (DNIT / Plano Diretor)
    let larguraCalcada = 2.0; // Padrão passeio público (ABNT NBR 9050)

    if (!tags) return { larguraPista, larguraCalcada };

    // 1. Tag explícita de largura da via (width / est_width / width:carriageway)
    const rawWidth = tags.width || tags.est_width || tags['width:carriageway'];
    if (rawWidth) {
        const parsed = parseFloat(String(rawWidth).replace(',', '.').replace(/[^\d.]/g, ''));
        if (!isNaN(parsed) && parsed >= 2.5 && parsed <= 40.0) {
            larguraPista = parsed;
        }
    } else if (tags.lanes) {
        const lanes = parseInt(tags.lanes, 10);
        if (!isNaN(lanes) && lanes >= 1 && lanes <= 8) {
            larguraPista = Math.max(5.0, lanes * 3.25);
        }
    } else if (tags.highway) {
        switch (tags.highway) {
            case 'motorway':
            case 'trunk':
                larguraPista = 14.0;
                break;
            case 'primary':
                larguraPista = 10.5;
                break;
            case 'secondary':
                larguraPista = 9.0;
                break;
            case 'tertiary':
                larguraPista = 8.0;
                break;
            case 'residential':
                larguraPista = 7.0;
                break;
            case 'unclassified':
            case 'living_street':
                larguraPista = 6.0;
                break;
            case 'service':
                larguraPista = 4.5;
                larguraCalcada = 1.2;
                break;
            case 'track':
            case 'path':
            case 'footway':
            case 'pedestrian':
                larguraPista = 3.0;
                larguraCalcada = 1.0;
                break;
            default:
                larguraPista = 7.0;
                break;
        }
    }

    // 2. Tag explícita de largura de calçada/passeio
    const rawSidewalk = tags['sidewalk:width'] || tags['sidewalk:both:width'] || tags['width:sidewalk'];
    if (rawSidewalk) {
        const parsedSw = parseFloat(String(rawSidewalk).replace(',', '.').replace(/[^\d.]/g, ''));
        if (!isNaN(parsedSw) && parsedSw >= 0.8 && parsedSw <= 6.0) {
            larguraCalcada = parsedSw;
        }
    }

    return { larguraPista, larguraCalcada };
}

function obterFusoAtual() {
    const selectFuso = document.getElementById('selectFuso');
    if (selectFuso) {
        const fusoSelecionado = parseInt(selectFuso.value, 10);
        if (!isNaN(fusoSelecionado) && fusoSelecionado > 0) {
            return fusoSelecionado;
        }
    }

    if (window.AppState && !isNaN(parseInt(window.AppState.fuso, 10))) {
        return parseInt(window.AppState.fuso, 10);
    }

    if (window.AppState && !isNaN(parseInt(window.AppState.fusoUtm, 10))) {
        return parseInt(window.AppState.fusoUtm, 10);
    }

    return 23;
}

/**
 * Converte coordenadas WGS84 para UTM e envia para o CAD via C#
 */
function converterEEnviarParaCad(elementos) {
    if (!elementos) return;
    if (!ViasObstrucoesState.projectScope || ViasObstrucoesState.projectGeneration < 0) {
        console.warn('[OSMPALETA][ESCOPO] Envio ao CAD bloqueado: ProjectScope não vinculado.');
        return;
    }
    const fuso = obterFusoAtual();
    const snyder = window.Snyder || (typeof Snyder !== 'undefined' ? Snyder : null);
    if (!snyder || typeof snyder.latLonToUtm !== 'function') {
        console.warn('[Vias CAD] Snyder geodésico indisponível para conversão UTM.');
        return;
    }

    function converterLista(lista) {
        if (!lista || !Array.isArray(lista)) return [];
        return lista.map(item => ({
            osmId: item.osmId,
            osmType: item.osmType || 'way',
            tipo: item.tipo,
            nome: item.nome || '',
            larguraPista: item.larguraPista || 7.0,
            larguraCalcada: item.larguraCalcada || 2.0,
            pontosUtm: item.coords.map(c => {
                const utm = snyder.latLonToUtm(c[0], c[1], fuso);
                return [utm.x, utm.y];
            })
        }));
    }

    const viasUtm = converterLista(elementos.vias);
    const calcadasUtm = converterLista(elementos.calcadas);
    const obstrucoesUtm = converterLista(elementos.obstrucoes);

    const totalElementos = viasUtm.length + calcadasUtm.length + obstrucoesUtm.length;
    if (totalElementos === 0) {
        console.warn('[OSMPALETA][PAYLOAD] Nenhum elemento foi convertido para UTM; payload não enviado ao CAD.', {
            fuso,
            vias: viasUtm.length,
            calcadas: calcadasUtm.length,
            obstrucoes: obstrucoesUtm.length,
            entradas: elementos
        });
        return;
    }

    const payload = {
        action: 'desenhar_elementos_urbanos',
        projectScope: {
            sobId: ViasObstrucoesState.projectScope,
            generation: ViasObstrucoesState.projectGeneration
        },
        fuso,
        vias: viasUtm,
        calcadas: calcadasUtm,
        obstrucoes: obstrucoesUtm
    };

    console.log('[OSMPALETA][PAYLOAD]', {
        action: payload.action,
        fuso,
        vias: payload.vias.length,
        calcadas: payload.calcadas.length,
        obstrucoes: payload.obstrucoes.length,
        totalElementos,
        totalVertices: payload.vias.reduce((s, item) => s + item.pontosUtm.length, 0)
            + payload.calcadas.reduce((s, item) => s + item.pontosUtm.length, 0)
            + payload.obstrucoes.reduce((s, item) => s + item.pontosUtm.length, 0),
        amostraPrimeiraVia: payload.vias[0] ? payload.vias[0].pontosUtm.slice(0, 3) : [],
        amostraPrimeiraCalcada: payload.calcadas[0] ? payload.calcadas[0].pontosUtm.slice(0, 3) : []
    });

    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage(payload);
        if (typeof showToast === 'function') {
            showToast(`🛣️ ${viasUtm.length} vias/ruas enviadas para desenho no AutoCAD!`, 'success');
        }
    }
}

// Exporta para o escopo global
window.ViasObstrucoesState = ViasObstrucoesState;
window.toggleViasObstrucoes = toggleViasObstrucoes;
window.carregarContextoUrbano = carregarContextoUrbano;
window.desenharViasNoCad = desenharViasNoCad;
window.calcularBbox = calcularBbox;
window.renderizarElementosOsm = renderizarElementosOsm;
window.executarConsultaOsm = executarConsultaOsm;
window.executarConsultaOverpass = executarConsultaOsm;
window.sincronizarOpcaoViasCad = sincronizarOpcaoViasCad;
window.inicializarOpcaoViasCad = inicializarOpcaoViasCad;
window.aplicarProjectScopeOsm = invalidarEstadoOsmPorProjectScope;
window.handleProjectScopeChanged = invalidarEstadoOsmPorProjectScope;

// Inicializa preferências de vias assim que o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarOpcaoViasCad);
} else {
    inicializarOpcaoViasCad();
}
