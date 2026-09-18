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
async function executarConsultaOsm(bbox) {
    if (!bbox) return null;

    // 1. API Oficial do OpenStreetMap (0.6 map.json)
    const urlOsm = `https://api.openstreetmap.org/api/0.6/map.json?bbox=${bbox.west.toFixed(6)},${bbox.south.toFixed(6)},${bbox.east.toFixed(6)},${bbox.north.toFixed(6)}`;
    try {
        const res = await fetch(urlOsm, {
            method: 'GET',
            headers: {
                'Accept': 'application/json, application/xml, text/xml, */*'
            },
            signal: AbortSignal.timeout(8000)
        });

        if (res.ok) {
            const rawText = await res.text();
            if (rawText && rawText.trim().length > 0) {
                const trimmed = rawText.trim();
                if (trimmed.startsWith('<')) {
                    const parser = new DOMParser();
                    const xmlDoc = parser.parseFromString(trimmed, 'text/xml');
                    const parsedData = converterOsmXmlParaJson(xmlDoc);
                    if (parsedData && parsedData.elements && parsedData.elements.length > 0) {
                        return parsedData;
                    }
                } else {
                    const data = JSON.parse(trimmed);
                    if (data && data.elements && Array.isArray(data.elements) && data.elements.length > 0) {
                        return data;
                    }
                }
            }
        }
    } catch (err) {
        console.warn('[Vias OSM] Falha ou timeout na API oficial OSM, tentando fallback Overpass...', err);
    }

    // 2. Fallbacks Overpass API com endpoints resilientes
    const bboxStr = `${bbox.south.toFixed(5)},${bbox.west.toFixed(5)},${bbox.north.toFixed(5)},${bbox.east.toFixed(5)}`;
    const queryOverpass = `[out:json][timeout:15];(way["highway"](${bboxStr});way["building"](${bboxStr});way["barrier"](${bboxStr}););out body geom;>;out skel qt;`;
    const bodyData = 'data=' + encodeURIComponent(queryOverpass);

    const fallbackEndpoints = [
        'https://overpass.private.coffee/api/interpreter',
        'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
    ];

    for (const ep of fallbackEndpoints) {
        try {
            const res = await fetch(ep, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
                },
                body: bodyData,
                signal: AbortSignal.timeout(12000)
            });
            if (!res.ok) continue;
            const data = await res.json();
            if (data && data.elements && Array.isArray(data.elements) && data.elements.length > 0) {
                return data;
            }
        } catch (err) {
            // Tenta próximo endpoint com fallback automático
        }
    }

    return null;
}

/**
 * Carrega vias, calçadas e edificações/obstruções da OpenStreetMap API
 */
async function carregarContextoUrbano(lat, lon, raioMetros = 150, mapa = null, forcarCad = false) {
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
    const data = await executarConsultaOsm(bbox);
    ViasObstrucoesState.carregando = false;

    if (data && data.elements) {
        ViasObstrucoesState.cacheGrid.add(gridKey);
        renderizarElementosOsm(data, ViasObstrucoesState.ativo ? mapa : null, querCad);
    } else {
        console.warn('[Vias/Obstruções OSM] Falha temporária nos servidores OSM para a coordenada:', lat, lon);
    }
}

/**
 * Força o desenho das vias e passeios no AutoCAD cobrindo a área da rede/mapa
 */
async function desenharViasNoCad(forcarReconsulta = false, mapa = null) {
    const map = mapa || (window.AppState ? window.AppState.map : null);
    
    if (forcarReconsulta) {
        ViasObstrucoesState.cacheGrid.clear();
        ViasObstrucoesState.waysProcessados.clear();
    }
    
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

    const data = await executarConsultaOsm(bbox);

    if (data && data.elements) {
        renderizarElementosOsm(data, map, true);
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
function renderizarElementosOsm(osmData, mapa, enviarCad = false) {
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
        if (el.type !== 'way') return;

        // Evita reprocessar o mesmo way já desenhado no CAD/Leaflet
        if (el.id && ViasObstrucoesState.waysProcessados.has(el.id)) return;
        if (el.id) ViasObstrucoesState.waysProcessados.add(el.id);

        let coords = [];
        if (el.geometry && Array.isArray(el.geometry)) {
            coords = el.geometry.map(g => [g.lat, g.lon]);
        } else if (el.nodes && Array.isArray(el.nodes)) {
            coords = el.nodes.map(nodeId => nodes[nodeId]).filter(Boolean);
        }
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
            const { larguraPista, larguraCalcada } = calcularLargurasVia(tags);

            if (mapa && ViasObstrucoesState.camadaVias) {
                const viaLinha = L.polyline(coords, {
                    color: '#334155', // Asfalto escuro
                    weight: Math.min(8, Math.max(3, larguraPista * 0.8)),
                    opacity: 0.75
                }).bindTooltip(`<b>🛣️ ${nomeRua}</b> (${tags.highway} - Pista: ${larguraPista.toFixed(1)}m, Passeio: ${larguraCalcada.toFixed(1)}m)`, { sticky: true });

                ViasObstrucoesState.camadaVias.addLayer(viaLinha);
            }
            novosElementos.vias.push({ 
                tipo: 'EIXO_VIA', 
                nome: nomeRua, 
                coords, 
                larguraPista, 
                larguraCalcada 
            });
        }
    });

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

/**
 * Converte coordenadas WGS84 para UTM e envia para o CAD via C#
 */
function converterEEnviarParaCad(elementos) {
    if (!elementos) return;
    const fuso = (window.AppState && window.AppState.fusoUtm) ? window.AppState.fusoUtm : 23;
    const snyder = window.Snyder || (typeof Snyder !== 'undefined' ? Snyder : null);
    if (!snyder || typeof snyder.latLonToUtm !== 'function') {
        console.warn('[Vias CAD] Snyder geodésico indisponível para conversão UTM.');
        return;
    }

    function converterLista(lista) {
        if (!lista || !Array.isArray(lista)) return [];
        return lista.map(item => ({
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
    if (totalElementos === 0) return;

    const payload = {
        action: 'desenhar_elementos_urbanos',
        fuso,
        vias: viasUtm,
        calcadas: calcadasUtm,
        obstrucoes: obstrucoesUtm
    };

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

// Inicializa preferências de vias assim que o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarOpcaoViasCad);
} else {
    inicializarOpcaoViasCad();
}

