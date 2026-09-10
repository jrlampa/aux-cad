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

// Estado da Aplicação
const AppState = {
    map: null,
    marker: null,
    currentLat: -22.9068,
    currentLon: -43.1729,
    currentX: 687450.0,
    currentY: 7465800.0,
    fuso: 23,
    activeLayer: 'osm',
    layers: {},
    dwgMarkersLayer: null
};

// Inicialização do Mapa
function initMap() {
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

    AppState.map = L.map('map', {
        center: [AppState.currentLat, AppState.currentLon],
        zoom: 17,
        layers: [AppState.layers.osm],
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
    }).addTo(AppState.map);

    // Eventos do Marcador e Mapa
    AppState.marker.on('dragend', function (e) {
        const pos = e.target.getLatLng();
        atualizarPosicao(pos.lat, pos.lng);
    });

    AppState.map.on('click', function (e) {
        AppState.marker.setLatLng(e.latlng);
        atualizarPosicao(e.latlng.lat, e.latlng.lng);
    });

    // Atualiza posição inicial
    atualizarPosicao(AppState.currentLat, AppState.currentLon);
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
    }

    btnOsm.addEventListener('click', () => switchLayer('osm', btnOsm));
    btnEsri.addEventListener('click', () => switchLayer('esri', btnEsri));
    btnGoogle.addEventListener('click', () => switchLayer('google', btnGoogle));
}

// Configuração de Formulários e Chips
function setupForms() {
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
        AppState.marker.setLatLng([geo.lat, geo.lon]);
        AppState.map.flyTo([geo.lat, geo.lon], 18);
        atualizarPosicao(geo.lat, geo.lon);
        showToast('Marcador atualizado no mapa.', 'success');
    });

    // Fuso UTM alterado
    document.getElementById('selectFuso').addEventListener('change', () => {
        atualizarPosicao(AppState.currentLat, AppState.currentLon);
    });

    // Chips de Equipamentos (Multi-seleção)
    document.querySelectorAll('#equipChips .chip').forEach(chip => {
        chip.addEventListener('click', () => {
            chip.classList.toggle('selected');
        });
    });

    // Conversão Bidirecional kVA <-> kW (FP = 0.92)
    const inputKva = document.getElementById('inputKva');
    const inputKw = document.getElementById('inputKw');

    inputKva.addEventListener('input', () => {
        const kva = parseFloat(inputKva.value);
        if (!isNaN(kva) && kva > 0) {
            inputKw.value = (kva * 0.92).toFixed(1);
        } else {
            inputKw.value = '';
        }
    });

    inputKw.addEventListener('input', () => {
        const kw = parseFloat(inputKw.value);
        if (!isNaN(kw) && kw > 0) {
            inputKva.value = (kw / 0.92).toFixed(1);
        } else {
            inputKva.value = '';
        }
    });

    // Chips de Carga Rápida
    document.querySelectorAll('#cargaChips .chip-sm').forEach(chip => {
        chip.addEventListener('click', () => {
            const kw = parseFloat(chip.getAttribute('data-kw'));
            inputKw.value = kw;
            inputKva.value = (kw / 0.92).toFixed(1);
        });
    });

    // Ação: Inserir no CAD
    document.getElementById('btnInserirCad').addEventListener('click', inserirPosteNoCad);

    // Ação: Ler do CAD
    document.getElementById('btnLerCadTop').addEventListener('click', lerPontoDoCad);

    // Ação: Sincronizar DWG
    document.getElementById('btnSincDwg').addEventListener('click', sincronizarDwg);
}

// Monta o payload e envia para o C# (.NET)
function inserirPosteNoCad() {
    const x = parseFloat(document.getElementById('inputX').value);
    const y = parseFloat(document.getElementById('inputY').value);
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
                AppState.marker.setLatLng([data.lat, data.lon]);
                AppState.map.flyTo([data.lat, data.lon], 19);
                atualizarPosicao(data.lat, data.lon);
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
