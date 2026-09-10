/**
 * Script de Controle da Paleta Cartográfica OSM & AutoCAD
 * Comunicação bidirecional com C# via Microsoft Edge WebView2
 */

// Conversor Geodésico Snyder Analítico no Frontend (Zero latência)
const Snyder = {
    A: 6378137.0,
    F: 1.0 / 298.257223563,
    K0: 0.9996,
    FALSE_EASTING: 500000.0,
    FALSE_NORTHING_S: 10000000.0,

    latLonToUtm(lat, lon, forcedZone = 23) {
        const zone = forcedZone || Math.floor((lon + 180.0) / 6.0) + 1;
        const latRad = lat * Math.PI / 180.0;
        const lonRad = lon * Math.PI / 180.0;
        const lon0Rad = ((zone - 1) * 6 - 180 + 3) * Math.PI / 180.0;

        const b = this.A * (1.0 - this.F);
        const e2 = (this.A * this.A - b * b) / (this.A * this.A);
        const ep2 = (this.A * this.A - b * b) / (b * b);

        const sinLat = Math.sin(latRad);
        const cosLat = Math.cos(latRad);
        const tanLat = Math.tan(latRad);

        const n = this.A / Math.sqrt(1.0 - e2 * sinLat * sinLat);
        const t = tanLat * tanLat;
        const c = ep2 * cosLat * cosLat;
        const p = (lonRad - lon0Rad);

        const m = this.A * ((1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * Math.pow(e2, 3) / 256.0) * latRad
            - (3.0 * e2 / 8.0 + 3.0 * e2 * e2 / 32.0 + 45.0 * Math.Pow ? Math.pow(e2, 3) : Math.pow(e2, 3) / 1024.0) * Math.sin(2.0 * latRad)
            + (15.0 * e2 * e2 / 256.0 + 45.0 * Math.pow(e2, 3) / 1024.0) * Math.sin(4.0 * latRad)
            - (35.0 * Math.pow(e2, 3) / 3072.0) * Math.sin(6.0 * latRad));

        const easting = this.FALSE_EASTING + this.K0 * n * (p * cosLat
            + Math.pow(p, 3) * Math.pow(cosLat, 3) / 6.0 * (1.0 - t + c)
            + Math.pow(p, 5) * Math.pow(cosLat, 5) / 120.0 * (5.0 - 18.0 * t + t * t + 72.0 * c - 58.0 * ep2));

        let northing = this.K0 * (m + n * tanLat * (p * p * cosLat * cosLat / 2.0
            + Math.pow(p, 4) * Math.pow(cosLat, 4) / 24.0 * (5.0 - t + 9.0 * c + 4.0 * c * c)
            + Math.pow(p, 6) * Math.pow(cosLat, 6) / 720.0 * (61.0 - 58.0 * t + t * t + 600.0 * c - 330.0 * ep2)));

        if (lat < 0) {
            northing += this.FALSE_NORTHING_S;
        }

        return { x: Math.round(easting * 100) / 100, y: Math.round(northing * 100) / 100, zone };
    },

    utmToLatLon(x, y, zone = 23) {
        const lon0Rad = ((zone - 1) * 6 - 180 + 3) * Math.PI / 180.0;
        const b = this.A * (1.0 - this.F);
        const e2 = (this.A * this.A - b * b) / (this.A * this.A);
        const ep2 = (this.A * this.A - b * b) / (b * b);
        const e1 = (1.0 - Math.sqrt(1.0 - e2)) / (1.0 + Math.sqrt(1.0 - e2));

        const dx = x - this.FALSE_EASTING;
        const dy = y - this.FALSE_NORTHING_S;

        const m = dy / this.K0;
        const mu = m / (this.A * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * Math.pow(e2, 3) / 256.0));

        const phi1 = mu
            + (3.0 * e1 / 2.0 - 27.0 * Math.pow(e1, 3) / 32.0) * Math.sin(2.0 * mu)
            + (21.0 * e1 * e1 / 16.0 - 55.0 * Math.pow(e1, 4) / 32.0) * Math.sin(4.0 * mu)
            + (151.0 * Math.pow(e1, 3) / 96.0) * Math.sin(6.0 * mu);

        const sinPhi1 = Math.sin(phi1);
        const cosPhi1 = Math.cos(phi1);
        const tanPhi1 = Math.tan(phi1);

        const n1 = this.A / Math.sqrt(1.0 - e2 * sinPhi1 * sinPhi1);
        const t1 = tanPhi1 * tanPhi1;
        const c1 = ep2 * cosPhi1 * cosPhi1;
        const r1 = this.A * (1.0 - e2) / Math.pow(1.0 - e2 * sinPhi1 * sinPhi1, 1.5);
        const d = dx / (n1 * this.K0);

        const latRad = phi1 - (n1 * tanPhi1 / r1) * (d * d / 2.0
            - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * ep2) * Math.pow(d, 4) / 24.0);

        const lonRad = lon0Rad + (d
            - (1.0 + 2.0 * t1 + c1) * Math.pow(d, 3) / 6.0) / cosPhi1;

        return {
            lat: latRad * 180.0 / Math.PI,
            lon: lonRad * 180.0 / Math.PI
        };
    }
};

// Chave de Persistência Local
const STORAGE_KEY = 'AUXCAD_PALETA_STATE';

// Estado da Aplicação
const AppState = {
    map: null,
    marker: null,
    hasMarker: true,
    currentLat: -22.9068,
    currentLon: -43.1729,
    currentX: 687450.0,
    currentY: 7465800.0,
    fuso: 23,
    activeLayer: 'osm',
    layers: {},
    dwgMarkersLayer: null
};

// Salva o estado completo no localStorage
function salvarEstadoPersistido() {
    try {
        const equips = [];
        document.querySelectorAll('#equipChips .chip.selected').forEach(c => {
            equips.push(c.getAttribute('data-val'));
        });

        const estado = {
            lat: AppState.currentLat,
            lon: AppState.currentLon,
            zoom: AppState.map ? AppState.map.getZoom() : 17,
            mapCenter: AppState.map ? AppState.map.getCenter() : null,
            hasMarker: AppState.hasMarker,
            fuso: AppState.fuso,
            numero: document.getElementById('inputNumero').value,
            tipoPoste: document.getElementById('selectTipoPoste').value,
            estruturaMt: document.getElementById('selectEstruturaMt').value,
            estruturaBt: document.getElementById('selectEstruturaBt').value,
            equipamentos: equips,
            kva: document.getElementById('inputKva').value,
            kw: document.getElementById('inputKw').value,
            autoInc: document.getElementById('chkAutoInc').checked,
            activeLayer: AppState.activeLayer
        };

        localStorage.setItem(STORAGE_KEY, JSON.stringify(estado));
    } catch (e) {
        console.warn('Falha ao persistir estado:', e);
    }
}

// Carrega o estado persistido do localStorage
function carregarEstadoPersistido() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (e) {
        console.warn('Falha ao ler estado persistido:', e);
        return null;
    }
}

// Inicialização do Mapa
function initMap() {
    const salvo = carregarEstadoPersistido();

    if (salvo) {
        if (salvo.lat && salvo.lon) {
            AppState.currentLat = salvo.lat;
            AppState.currentLon = salvo.lon;
        }
        if (salvo.fuso) AppState.fuso = salvo.fuso;
        if (salvo.hasMarker !== undefined) AppState.hasMarker = salvo.hasMarker;
        if (salvo.activeLayer) AppState.activeLayer = salvo.activeLayer;
    }

    AppState.layers.osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    });

    AppState.layers.esri = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: '© Esri Satellite'
    });

    AppState.layers.google = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        attribution: '© Google'
    });

    const initialLayer = AppState.layers[AppState.activeLayer] || AppState.layers.osm;
    const initialCenter = (salvo && salvo.mapCenter) ? [salvo.mapCenter.lat, salvo.mapCenter.lng] : [AppState.currentLat, AppState.currentLon];
    const initialZoom = (salvo && salvo.zoom) ? salvo.zoom : 17;

    AppState.map = L.map('map', {
        center: initialCenter,
        zoom: initialZoom,
        layers: [initialLayer],
        zoomControl: true
    });

    // Camada para postes vindos do DWG
    AppState.dwgMarkersLayer = L.layerGroup().addTo(AppState.map);

    // Marcador Principal Arrastável
    const customIcon = L.divIcon({
        className: 'custom-pole-marker',
        html: '<div style="background:#0284C7;width:18px;height:18px;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;color:white;font-size:10px;font-weight:bold;">⚡</div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });

    AppState.marker = L.marker([AppState.currentLat, AppState.currentLon], {
        draggable: true,
        icon: customIcon
    });

    // Adiciona ao mapa somente se o marcador estiver ativo
    if (AppState.hasMarker) {
        AppState.marker.addTo(AppState.map);
    }

    // Eventos do Marcador
    AppState.marker.on('dragend', function (e) {
        const pos = e.target.getLatLng();
        atualizarPosicao(pos.lat, pos.lng);
        salvarEstadoPersistido();
    });

    // Botão direito no marcador para removê-lo rapidamente
    AppState.marker.on('contextmenu', function (e) {
        L.DomEvent.stopPropagation(e);
        apagarMarcador();
    });

    // Clique no Mapa reposiciona ou recria o marcador
    AppState.map.on('click', function (e) {
        posicionarMarcador(e.latlng.lat, e.latlng.lng);
    });

    // Salva centro e zoom ao navegar no mapa
    AppState.map.on('moveend', function () {
        salvarEstadoPersistido();
    });

    // Se o marcador estiver ativo, atualiza as coordenadas na tela
    if (AppState.hasMarker) {
        atualizarPosicao(AppState.currentLat, AppState.currentLon);
    } else {
        document.getElementById('inputX').value = '';
        document.getElementById('inputY').value = '';
    }

    // Restaura campos persistidos
    if (salvo) {
        if (salvo.numero) document.getElementById('inputNumero').value = salvo.numero;
        if (salvo.tipoPoste) document.getElementById('selectTipoPoste').value = salvo.tipoPoste;
        if (salvo.estruturaMt !== undefined) document.getElementById('selectEstruturaMt').value = salvo.estruturaMt;
        if (salvo.estruturaBt) document.getElementById('selectEstruturaBt').value = salvo.estruturaBt;
        if (salvo.fuso) document.getElementById('selectFuso').value = salvo.fuso;
        if (salvo.kva) document.getElementById('inputKva').value = salvo.kva;
        if (salvo.kw) document.getElementById('inputKw').value = salvo.kw;
        if (salvo.autoInc !== undefined) document.getElementById('chkAutoInc').checked = salvo.autoInc;

        if (Array.isArray(salvo.equipamentos)) {
            document.querySelectorAll('#equipChips .chip').forEach(c => {
                if (salvo.equipamentos.includes(c.getAttribute('data-val'))) {
                    c.classList.add('selected');
                }
            });
        }
    }
}

// Posiciona e exibe o marcador no mapa
function posicionarMarcador(lat, lon) {
    if (!AppState.map.hasLayer(AppState.marker)) {
        AppState.marker.addTo(AppState.map);
    }
    AppState.marker.setLatLng([lat, lon]);
    AppState.hasMarker = true;
    atualizarPosicao(lat, lon);
    salvarEstadoPersistido();
}

// Apaga apenas o marcador do mapa
function apagarMarcador() {
    if (AppState.map && AppState.marker && AppState.map.hasLayer(AppState.marker)) {
        AppState.map.removeLayer(AppState.marker);
    }
    AppState.hasMarker = false;
    document.getElementById('inputX').value = '';
    document.getElementById('inputY').value = '';
    salvarEstadoPersistido();
    showToast('Marcador removido. Clique no mapa para posicionar novamente.', 'info');
}

// Limpa campos do formulário para o estado padrão
function limparFormulario() {
    document.querySelectorAll('#equipChips .chip.selected').forEach(c => {
        c.classList.remove('selected');
    });
    document.getElementById('selectTipoPoste').value = '11/600';
    document.getElementById('selectEstruturaMt').value = '';
    document.getElementById('selectEstruturaBt').value = 'S1';
    document.getElementById('inputKva').value = '';
    document.getElementById('inputKw').value = '';
    salvarEstadoPersistido();
    showToast('Campos do formulário resetados.', 'info');
}

// Atualiza coordenadas nos inputs
function atualizarPosicao(lat, lon) {
    AppState.currentLat = lat;
    AppState.currentLon = lon;

    const fuso = parseInt(document.getElementById('selectFuso').value, 10) || 23;
    const utm = Snyder.latLonToUtm(lat, lon, fuso);

    AppState.currentX = utm.x;
    AppState.currentY = utm.y;
    AppState.fuso = fuso;

    document.getElementById('inputX').value = utm.x.toFixed(2);
    document.getElementById('inputY').value = utm.y.toFixed(2);
    document.getElementById('coordBadge').textContent = `Fuso ${fuso}S`;
}

// Alternância de Camadas
function setupLayerButtons() {
    const btnOsm = document.getElementById('btnLayerOsm');
    const btnEsri = document.getElementById('btnLayerEsri');
    const btnGoogle = document.getElementById('btnLayerGoogle');

    function switchLayer(layerName, activeBtn) {
        Object.values(AppState.layers).forEach(l => AppState.map.removeLayer(l));
        AppState.map.addLayer(AppState.layers[layerName]);
        [btnOsm, btnEsri, btnGoogle].forEach(b => b.classList.remove('active'));
        activeBtn.classList.add('active');
        AppState.activeLayer = layerName;
        salvarEstadoPersistido();
    }

    btnOsm.addEventListener('click', () => switchLayer('osm', btnOsm));
    btnEsri.addEventListener('click', () => switchLayer('esri', btnEsri));
    btnGoogle.addEventListener('click', () => switchLayer('google', btnGoogle));

    // Ativa botão da camada persistida
    if (AppState.activeLayer === 'esri') btnEsri.classList.add('active'), btnOsm.classList.remove('active');
    else if (AppState.activeLayer === 'google') btnGoogle.classList.add('active'), btnOsm.classList.remove('active');
}

// Configuração de Formulários e Chips
function setupForms() {
    // Ação: Apagar Marcador
    document.getElementById('btnApagarMarcador')?.addEventListener('click', apagarMarcador);

    // Ação: Limpar Formulário
    document.getElementById('btnLimparForm')?.addEventListener('click', limparFormulario);

    // Aplicar coordenadas digitadas
    document.getElementById('btnAplicarCoord').addEventListener('click', () => {
        const x = parseFloat(document.getElementById('inputX').value);
        const y = parseFloat(document.getElementById('inputY').value);
        const fuso = parseInt(document.getElementById('selectFuso').value, 10) || 23;

        if (isNaN(x) || isNaN(y)) {
            showToast('Por favor, informe valores numéricos para X e Y.', 'error');
            return;
        }

        const geo = Snyder.utmToLatLon(x, y, fuso);
        posicionarMarcador(geo.lat, geo.lon);
        AppState.map.flyTo([geo.lat, geo.lon], 18);
        showToast('Marcador atualizado no mapa.', 'success');
    });

    // Fuso UTM alterado
    document.getElementById('selectFuso').addEventListener('change', () => {
        if (AppState.hasMarker) {
            atualizarPosicao(AppState.currentLat, AppState.currentLon);
            salvarEstadoPersistido();
        }
    });

    // Chips de Equipamentos (Multi-seleção)
    document.querySelectorAll('#equipChips .chip').forEach(chip => {
        chip.addEventListener('click', () => {
            chip.classList.toggle('selected');
            salvarEstadoPersistido();
        });
    });

    // Persistência automática em inputs
    ['inputNumero', 'selectTipoPoste', 'selectEstruturaMt', 'selectEstruturaBt', 'chkAutoInc'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', salvarEstadoPersistido);
            if (el.tagName === 'INPUT') el.addEventListener('input', salvarEstadoPersistido);
        }
    });

    // Conversão Bidirecional kVA <-> kW (FP = 0.92)
    const inputKva = document.getElementById('inputKva');
    const inputKw = document.getElementById('inputKw');

    inputKva.addEventListener('input', () => {
        const kva = parseFloat(inputKva.value);
        inputKw.value = (!isNaN(kva) && kva > 0) ? (kva * 0.92).toFixed(1) : '';
        salvarEstadoPersistido();
    });

    inputKw.addEventListener('input', () => {
        const kw = parseFloat(inputKw.value);
        inputKva.value = (!isNaN(kw) && kw > 0) ? (kw / 0.92).toFixed(1) : '';
        salvarEstadoPersistido();
    });

    // Chips de Carga Rápida
    document.querySelectorAll('#cargaChips .chip-sm').forEach(chip => {
        chip.addEventListener('click', () => {
            const kw = parseFloat(chip.getAttribute('data-kw'));
            inputKw.value = kw;
            inputKva.value = (kw / 0.92).toFixed(1);
            salvarEstadoPersistido();
        });
    });

    // Ações do Painel e CAD
    document.getElementById('btnInserirCad').addEventListener('click', inserirPosteNoCad);
    document.getElementById('btnLerCadTop').addEventListener('click', lerPontoDoCad);
    document.getElementById('btnSincDwg').addEventListener('click', sincronizarDwg);

    // Ação: Toggle Sidebar (Painel Lateral)
    const btnToggle = document.getElementById('btnToggleSidebar');
    const sidebar = document.getElementById('sidebar');
    if (btnToggle && sidebar) {
        btnToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            const isCollapsed = sidebar.classList.contains('collapsed');
            btnToggle.textContent = isCollapsed ? '📑 Painel ▶' : '📑 Painel ◀';
            setTimeout(() => {
                if (AppState.map) AppState.map.invalidateSize();
            }, 260);
        });
    }

    // Redimensionamento de janela recalcula Leaflet
    window.addEventListener('resize', () => {
        if (AppState.map) AppState.map.invalidateSize();
    });
}

// Monta o payload e envia para o C# (.NET)
function inserirPosteNoCad() {
    if (!AppState.hasMarker) {
        showToast('⚠️ Nenhum ponto marcado no mapa. Clique no mapa para posicionar!', 'error');
        return;
    }

    const x = parseFloat(document.getElementById('inputX').value);
    const y = parseFloat(document.getElementById('inputY').value);
    if (isNaN(x) || isNaN(y)) {
        showToast('Coordenadas X ou Y inválidas.', 'error');
        return;
    }

    const numero = document.getElementById('inputNumero').value.trim() || '01';
    const tipoPoste = document.getElementById('selectTipoPoste').value;
    const estruturaMt = document.getElementById('selectEstruturaMt').value;
    const estruturaBt = document.getElementById('selectEstruturaBt').value;
    const fuso = parseInt(document.getElementById('selectFuso').value, 10) || 23;

    // Equipamentos selecionados
    const equipamentos = [];
    document.querySelectorAll('#equipChips .chip.selected').forEach(c => {
        equipamentos.push(c.getAttribute('data-val'));
    });

    // Carga Especial Trifásica
    let cargaTri = '';
    const kva = parseFloat(document.getElementById('inputKva').value);
    const kw = parseFloat(document.getElementById('inputKw').value);
    if (!isNaN(kva) && kva > 0) {
        cargaTri = `CARGA TRI: ${kva.toFixed(1)}kVA (${kw.toFixed(1)}kW)`;
    }

    const payload = {
        action: 'inserir_poste',
        x,
        y,
        numero,
        tipoPoste,
        estruturaMt,
        estruturaBt,
        equipamentos,
        cargaTri,
        fusoUtm: fuso
    };

    enviarParaCSharp(payload);
    showToast(`Enviando poste ${numero} para o AutoCAD...`, 'info');

    // Auto-incrementar número se marcado
    if (document.getElementById('chkAutoInc').checked) {
        incrementarNumeroPoste();
    }
}

function incrementarNumeroPoste() {
    const input = document.getElementById('inputNumero');
    const val = input.value.trim();
    const num = parseInt(val, 10);
    if (!isNaN(num)) {
        const next = num + 1;
        input.value = next < 10 ? `0${next}` : `${next}`;
        salvarEstadoPersistido();
    }
}

function lerPontoDoCad() {
    const fuso = parseInt(document.getElementById('selectFuso').value, 10) || 23;
    enviarParaCSharp({ action: 'capturar_ponto', fuso });
    showToast('Clique em um ponto no AutoCAD...', 'info');
}

function sincronizarDwg() {
    const fuso = parseInt(document.getElementById('selectFuso').value, 10) || 23;
    enviarParaCSharp({ action: 'escanear_dwg', fuso });
    showToast('Lendo postes do desenho...', 'info');
}

// Comunicação com WebView2 (C#)
function enviarParaCSharp(obj) {
    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage(obj);
    } else {
        console.log('[WebView2 Mock]', obj);
        showToast('WebView2 indisponível (modo navegador).', 'error');
    }
}

// Escuta mensagens vindas do C#
function setupMensagensCSharp() {
    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.addEventListener('message', event => {
            const data = event.data;
            if (!data) return;

            if (data.action === 'ponto_capturado') {
                posicionarMarcador(data.lat, data.lon);
                AppState.map.flyTo([data.lat, data.lon], 19);
                showToast(`Ponto capturado do CAD: (${data.x.toFixed(2)}, ${data.y.toFixed(2)})`, 'success');
            }
            else if (data.action === 'resultado_insercao') {
                showToast(data.message, data.success ? 'success' : 'error');
            }
            else if (data.action === 'postes_dwg') {
                renderizarPostesDwg(data.postes || []);
            }
        });
    }
}

function renderizarPostesDwg(postes) {
    AppState.dwgMarkersLayer.clearLayers();
    postes.forEach(p => {
        const m = L.circleMarker([p.lat, p.lon], {
            radius: 5,
            fillColor: '#10B981',
            color: '#FFFFFF',
            weight: 1.5,
            fillOpacity: 0.9
        }).bindPopup(`<b>Poste DWG</b><br>X: ${p.x}<br>Y: ${p.y}`);
        AppState.dwgMarkersLayer.addLayer(m);
    });
    showToast(`${postes.length} postes sincronizados do DWG.`, 'success');
}

function showToast(msg, type = 'info') {
    const toast = document.getElementById('statusToast');
    toast.textContent = msg;
    toast.className = 'status-toast ' + type;
}

// Inicialização Geral
window.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupLayerButtons();
    setupForms();
    setupMensagensCSharp();
});
