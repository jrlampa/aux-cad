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
    carregando: false
};

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
    ViasObstrucoesState.desenharNoCad = ViasObstrucoesState.ativo;
    const btn = document.getElementById('btnToggleVias');

    if (btn) {
        if (ViasObstrucoesState.ativo) {
            btn.classList.add('active');
            btn.innerHTML = '🏙️ Vias: VISÍVEIS';
            if (typeof showToast === 'function') {
                showToast('🏙️ Vias urbanas ativadas (mapa e CAD)', 'info');
            }
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
 * Carrega vias, calçadas e edificações/obstruções da Overpass API
 */
async function carregarContextoUrbano(lat, lon, raioMetros = 120, mapa = null) {
    if (!ViasObstrucoesState.ativo) return;

    inicializarCamadasUrbanas(mapa);

    // Chave de quadrícula (~100m) para evitar consultas redundantes
    const gridKey = `${lat.toFixed(3)}_${lon.toFixed(3)}`;
    if (ViasObstrucoesState.cacheGrid.has(gridKey)) {
        // Se já consultou e temos elementos acumulados, garante envio ao CAD
        if (ViasObstrucoesState.desenharNoCad && window.chrome && window.chrome.webview) {
            converterEEnviarParaCad(ViasObstrucoesState.elementosAcumulados);
        }
        return;
    }
    ViasObstrucoesState.cacheGrid.add(gridKey);

    const bbox = calcularBbox(lat, lon, raioMetros);
    const bboxStr = `${bbox.south.toFixed(5)},${bbox.west.toFixed(5)},${bbox.north.toFixed(5)},${bbox.east.toFixed(5)}`;
    const queryOverpass = `[out:json][timeout:15];(way["highway"](${bboxStr});way["building"](${bboxStr});way["barrier"](${bboxStr}););out body;>;out skel qt;`;

    // Endpoints com fallback para resiliência de rede
    const endpoints = [
        'https://overpass-api.de/api/interpreter',
        'https://overpass.kumi.systems/api/interpreter',
        'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
    ];

    ViasObstrucoesState.carregando = true;
    let sucesso = false;

    for (const ep of endpoints) {
        try {
            const url = `${ep}?data=${encodeURIComponent(queryOverpass)}`;
            const res = await fetch(url, { signal: AbortSignal.timeout(12000) });
            if (!res.ok) continue;
            const data = await res.json();
            renderizarElementosOsm(data, mapa);
            sucesso = true;
            break;
        } catch (err) {
            // Tenta próximo endpoint
        }
    }

    if (!sucesso) {
        console.warn('[Vias/Obstruções OSM] Todos os endpoints Overpass indisponíveis temporariamente.');
    }

    ViasObstrucoesState.carregando = false;
}

/**
 * Força o desenho das vias e passeios no AutoCAD cobrindo a área da rede/mapa
 */
async function desenharViasNoCad(forcarReconsulta = false, mapa = null) {
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
    let bboxStr = '';
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
            const margem = 0.0015; // ~160 metros de margem
            bboxStr = `${(minLat - margem).toFixed(5)},${(minLon - margem).toFixed(5)},${(maxLat + margem).toFixed(5)},${(maxLon + margem).toFixed(5)}`;
        }
    }

    // Fallback: usar viewport visível do mapa ou coordenada central
    if (!bboxStr && map) {
        const bounds = map.getBounds();
        bboxStr = `${bounds.getSouth().toFixed(5)},${bounds.getWest().toFixed(5)},${bounds.getNorth().toFixed(5)},${bounds.getEast().toFixed(5)}`;
    } else if (!bboxStr && window.AppState && window.AppState.currentLat) {
        const bbox = calcularBbox(window.AppState.currentLat, window.AppState.currentLon, 250);
        bboxStr = `${bbox.south.toFixed(5)},${bbox.west.toFixed(5)},${bbox.north.toFixed(5)},${bbox.east.toFixed(5)}`;
    }

    if (!bboxStr) {
        if (typeof showToast === 'function') {
            showToast('Posicione o mapa ou trace um poste para localizar as vias.', 'warning');
        }
        return;
    }

    const queryOverpass = `[out:json][timeout:18];(way["highway"](${bboxStr});way["building"](${bboxStr});way["barrier"](${bboxStr}););out body;>;out skel qt;`;
    const endpoints = [
        'https://overpass-api.de/api/interpreter',
        'https://overpass.kumi.systems/api/interpreter',
        'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
    ];

    let sucesso = false;
    for (const ep of endpoints) {
        try {
            const url = `${ep}?data=${encodeURIComponent(queryOverpass)}`;
            const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
            if (!res.ok) continue;
            const data = await res.json();
            renderizarElementosOsm(data, map);
            sucesso = true;
            break;
        } catch (e) {
            // Próximo endpoint
        }
    }

    if (sucesso) {
        const nVias = ViasObstrucoesState.elementosAcumulados.vias.length;
        if (typeof showToast === 'function') {
            showToast(`🛣️ ${nVias} trechos de vias/passeios desenhados no CAD!`, 'success');
        }
    } else {
        if (typeof showToast === 'function') {
            showToast('Não foi possível obter os eixos de vias do OSM no momento.', 'warning');
        }
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

    const novosElementos = {
        vias: [],
        calcadas: [],
        obstrucoes: []
    };

    osmData.elements.forEach(el => {
        if (el.type !== 'way' || !el.nodes || el.nodes.length < 2) return;

        // Evita reprocessar o mesmo way já desenhado no CAD/Leaflet
        if (el.id && ViasObstrucoesState.waysProcessados.has(el.id)) return;
        if (el.id) ViasObstrucoesState.waysProcessados.add(el.id);

        const coords = el.nodes.map(nodeId => nodes[nodeId]).filter(Boolean);
        if (coords.length < 2) return;

        const tags = el.tags || {};

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
            novosElementos.obstrucoes.push({ tipo: 'EDIFICACAO', nome: nomeEdif, coords });
        }
        // 2. Muros e Barreiras (Obstruções Lineares)
        else if (tags.barrier) {
            if (mapa && ViasObstrucoesState.camadaObstrucoes) {
                const barreiraLinha = L.polyline(coords, {
                    color: '#dc2626', // Vermelho alerta
                    weight: 2,
                    dashArray: '3, 4',
                    opacity: 0.8
                }).bindTooltip(`<b>🚧 Barreira / Muro</b> (${tags.barrier})`, { sticky: true });

                ViasObstrucoesState.camadaObstrucoes.addLayer(barreiraLinha);
            }
            novosElementos.obstrucoes.push({ tipo: 'BARREIRA', nome: tags.barrier, coords });
        }
        // 3. Calçadas e Passeios Públicos
        else if (tags.footway === 'sidewalk' || tags.sidewalk || tags.highway === 'footway' || tags.highway === 'pedestrian') {
            if (mapa && ViasObstrucoesState.camadaCalcadas) {
                const calcadaLinha = L.polyline(coords, {
                    color: '#d97706', // Âmbar claro para passeio público
                    weight: 2.5,
                    dashArray: '2, 3',
                    opacity: 0.85
                }).bindTooltip('<b>🚶 Calçada / Passeio Público</b>', { sticky: true });

                ViasObstrucoesState.camadaCalcadas.addLayer(calcadaLinha);
            }
            novosElementos.calcadas.push({ tipo: 'PASSEIO', coords });
        }
        // 4. Vias e Ruas (Pistas de Rolamento / Eixos)
        else if (tags.highway) {
            const nomeRua = tags.name || tags['ref'] || 'Via Pública';
            if (mapa && ViasObstrucoesState.camadaVias) {
                const viaLinha = L.polyline(coords, {
                    color: '#334155', // Asfalto escuro
                    weight: 4.5,
                    opacity: 0.75
                }).bindTooltip(`<b>🛣️ ${nomeRua}</b> (${tags.highway})`, { sticky: true });

                ViasObstrucoesState.camadaVias.addLayer(viaLinha);
            }
            novosElementos.vias.push({ tipo: 'EIXO_VIA', nome: nomeRua, coords });
        }
    });

    // Acumula elementos no estado global
    ViasObstrucoesState.elementosAcumulados.vias.push(...novosElementos.vias);
    ViasObstrucoesState.elementosAcumulados.calcadas.push(...novosElementos.calcadas);
    ViasObstrucoesState.elementosAcumulados.obstrucoes.push(...novosElementos.obstrucoes);

    // Se o envio ao CAD estiver ativado, notifica o C# via WebView2
    if (ViasObstrucoesState.desenharNoCad && window.chrome && window.chrome.webview) {
        converterEEnviarParaCad(novosElementos);
    }
}

/**
 * Converte coordenadas WGS84 para UTM e envia para o CAD via C#
 */
function converterEEnviarParaCad(elementos) {
    if (!elementos) return;
    const fuso = (window.AppState && window.AppState.fusoUtm) ? window.AppState.fusoUtm : 23;
    if (!window.Snyder || typeof window.Snyder.latLonToUtm !== 'function') return;

    function converterLista(lista) {
        if (!lista || !Array.isArray(lista)) return [];
        return lista.map(item => ({
            tipo: item.tipo,
            nome: item.nome || '',
            pontosUtm: item.coords.map(c => {
                const utm = window.Snyder.latLonToUtm(c[0], c[1], fuso);
                return [utm.x, utm.y];
            })
        }));
    }

    const viasUtm = converterLista(elementos.vias);
    const calcadasUtm = converterLista(elementos.calcadas);
    const obstrucoesUtm = converterLista(elementos.obstrucoes);

    if (viasUtm.length === 0 && calcadasUtm.length === 0 && obstrucoesUtm.length === 0) return;

    const payload = {
        action: 'desenhar_elementos_urbanos',
        fuso,
        vias: viasUtm,
        calcadas: calcadasUtm,
        obstrucoes: obstrucoesUtm
    };

    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage(payload);
    }
}

// Exporta para o escopo global
window.ViasObstrucoesState = ViasObstrucoesState;
window.toggleViasObstrucoes = toggleViasObstrucoes;
window.carregarContextoUrbano = carregarContextoUrbano;
window.desenharViasNoCad = desenharViasNoCad;
window.calcularBbox = calcularBbox;
window.renderizarElementosOsm = renderizarElementosOsm;
window.sincronizarOpcaoViasCad = sincronizarOpcaoViasCad;
window.inicializarOpcaoViasCad = inicializarOpcaoViasCad;

// Inicializa preferências de vias assim que o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarOpcaoViasCad);
} else {
    inicializarOpcaoViasCad();
}

