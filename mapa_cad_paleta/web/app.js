/**
 * Script de Controle da Paleta Cartográfica OSM & AutoCAD
 * Comunicação bidirecional com C# via Microsoft Edge WebView2
 */

// Conversor Snyder carregado externamente via snyder.js

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
    dwgMarkersLayer: null,
    estruturasMt: [],
    estruturasBt: ['S1'],
    temTrafo: false,
    potenciaTrafo: '45kVA'
};

// Funções de Gerenciamento de Multi-Estruturas
function renderizarTagsEstruturas() {
    const cMt = document.getElementById('tagsEstruturasMt');
    if (cMt) {
        cMt.innerHTML = AppState.estruturasMt.map((mt, idx) => `
            <span class="structure-badge">
                ${mt}
                <button type="button" class="badge-remove" onclick="window.removerEstruturaMt(${idx})" title="Remover ${mt}">✕</button>
            </span>
        `).join('');
    }

    const cBt = document.getElementById('tagsEstruturasBt');
    if (cBt) {
        cBt.innerHTML = AppState.estruturasBt.map((bt, idx) => `
            <span class="structure-badge badge-bt">
                ${bt}
                <button type="button" class="badge-remove" onclick="window.removerEstruturaBt(${idx})" title="Remover ${bt}">✕</button>
            </span>
        `).join('');
    }
}

function adicionarEstruturaMt(nome) {
    if (nome?.trim()) { AppState.estruturasMt.push(nome.trim()); renderizarTagsEstruturas(); salvarEstadoPersistido(); }
}
function removerEstruturaMt(idx) {
    AppState.estruturasMt.splice(idx, 1); renderizarTagsEstruturas(); salvarEstadoPersistido();
}
function adicionarEstruturaBt(nome) {
    if (nome?.trim()) { AppState.estruturasBt.push(nome.trim()); renderizarTagsEstruturas(); salvarEstadoPersistido(); }
}
function removerEstruturaBt(idx) {
    AppState.estruturasBt.splice(idx, 1); renderizarTagsEstruturas(); salvarEstadoPersistido();
}

window.removerEstruturaMt = removerEstruturaMt;
window.removerEstruturaBt = removerEstruturaBt;

// Controle de Transformador
function setTrafoAtivo(ativo) {
    AppState.temTrafo = ativo;
    const chip = document.getElementById('chipTrafo');
    const painel = document.getElementById('painelTrafo');
    if (chip) {
        if (ativo) chip.classList.add('selected');
        else chip.classList.remove('selected');
    }
    if (painel) {
        painel.style.display = ativo ? 'block' : 'none';
    }
    atualizarLabelTrafo();
    salvarEstadoPersistido();
}

function atualizarLabelTrafo() {
    const lbl = document.getElementById('lblTrafoKva');
    if (lbl) {
        lbl.textContent = AppState.potenciaTrafo || '45kVA';
    }
}

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
            estruturasMt: AppState.estruturasMt,
            estruturasBt: AppState.estruturasBt,
            temTrafo: AppState.temTrafo,
            potenciaTrafo: AppState.potenciaTrafo,
            equipamentos: equips,
            mono: parseInt(document.getElementById('inputMono')?.value || '0', 10) || 0,
            bi: parseInt(document.getElementById('inputBi')?.value || '0', 10) || 0,
            tri: parseInt(document.getElementById('inputTri')?.value || '0', 10) || 0,
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

    // Clique no Mapa reposiciona marcador ou adiciona ponto na régua
    AppState.map.on('click', function (e) {
        if (window.MedicaoState?.ativo && typeof window.cliqueMapaMedicao === 'function') {
            window.cliqueMapaMedicao(e, AppState.map);
            return;
        }

        let targetLat = e.latlng.lat;
        let targetLon = e.latlng.lng;
        if (window.SnapMagnetico && typeof window.SnapMagnetico.buscarPontoSnap === 'function') {
            const snap = window.SnapMagnetico.buscarPontoSnap(e.latlng, AppState.map);
            if (snap.snapped) {
                targetLat = snap.lat;
                targetLon = snap.lon;
            }
        }
        posicionarMarcador(targetLat, targetLon);
    });

    // Movimentação do mouse atualiza linha elástica da régua ou indicador de snap magnético
    AppState.map.on('mousemove', function (e) {
        if (window.MedicaoState?.ativo && typeof window.mouseMoveMapaMedicao === 'function') {
            window.mouseMoveMapaMedicao(e, AppState.map);
        } else if (window.SnapMagnetico && typeof window.SnapMagnetico.buscarPontoSnap === 'function') {
            window.SnapMagnetico.buscarPontoSnap(e.latlng, AppState.map);
        }
    });

    AppState.map.on('mouseout', function () {
        if (window.SnapMagnetico && typeof window.SnapMagnetico.limparIndicador === 'function') {
            window.SnapMagnetico.limparIndicador(AppState.map);
        }
    });

    // Duplo clique finaliza medição
    AppState.map.on('dblclick', function (e) {
        if (window.MedicaoState?.ativo && typeof window.toggleModoMedicao === 'function') {
            L.DomEvent.stopPropagation(e);
            window.toggleModoMedicao(AppState.map);
        }
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
        if (salvo.fuso) document.getElementById('selectFuso').value = salvo.fuso;
        if (salvo.kva) document.getElementById('inputKva').value = salvo.kva;
        if (salvo.kw) document.getElementById('inputKw').value = salvo.kw;
        if (salvo.autoInc !== undefined) document.getElementById('chkAutoInc').checked = salvo.autoInc;

        if (Array.isArray(salvo.estruturasMt)) {
            AppState.estruturasMt = salvo.estruturasMt;
        } else if (salvo.estruturaMt) {
            AppState.estruturasMt = [salvo.estruturaMt];
        }

        if (Array.isArray(salvo.estruturasBt)) {
            AppState.estruturasBt = salvo.estruturasBt;
        } else if (salvo.estruturaBt) {
            AppState.estruturasBt = [salvo.estruturaBt];
        }

        if (salvo.potenciaTrafo) {
            AppState.potenciaTrafo = salvo.potenciaTrafo;
            const selPot = document.getElementById('selectPotenciaTrafo');
            if (selPot) {
                const optExists = Array.from(selPot.options).some(o => o.value === salvo.potenciaTrafo);
                if (optExists) {
                    selPot.value = salvo.potenciaTrafo;
                } else {
                    selPot.value = 'OUTRO';
                    const customPot = document.getElementById('inputPotenciaCustom');
                    if (customPot) {
                        customPot.value = salvo.potenciaTrafo;
                        customPot.style.display = 'block';
                    }
                }
            }
        }

        if (salvo.temTrafo !== undefined) {
            setTrafoAtivo(salvo.temTrafo);
        } else if (Array.isArray(salvo.equipamentos) && salvo.equipamentos.some(e => e.includes('TRAFO'))) {
            setTrafoAtivo(true);
        }

        if (Array.isArray(salvo.equipamentos)) {
            document.querySelectorAll('#equipChips .chip').forEach(c => {
                const v = c.getAttribute('data-val');
                if (v !== 'TRAFO' && salvo.equipamentos.includes(v)) {
                    c.classList.add('selected');
                }
            });
        }
    }

    renderizarTagsEstruturas();
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
    document.querySelectorAll('#equipChips .chip').forEach(c => {
        c.classList.remove('selected');
    });
    document.getElementById('selectTipoPoste').value = '11/600';
    AppState.estruturasMt = [];
    AppState.estruturasBt = ['S1'];
    setTrafoAtivo(false);
    AppState.potenciaTrafo = '45kVA';
    const selPot = document.getElementById('selectPotenciaTrafo');
    if (selPot) selPot.value = '45kVA';
    const customPot = document.getElementById('inputPotenciaCustom');
    if (customPot) {
        customPot.value = '';
        customPot.style.display = 'none';
    }
    renderizarTagsEstruturas();
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

    // Audita restrições ambientais em tempo real se a camada estiver ativa
    if (window.auditarPontoAmbiental) {
        window.auditarPontoAmbiental(lat, lon);
    }

    // Carrega contexto urbano (vias, calçadas e obstruções) em torno do ponto
    if (window.carregarContextoUrbano) {
        window.carregarContextoUrbano(lat, lon, 100, AppState.map);
    }
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

// ==========================================================================
// Funções de Gestão de Consumidores BT (CQT) e Formulário
// ==========================================================================
function alterarCliente(fase, delta) {
    const id = 'input' + fase;
    const input = document.getElementById(id);
    if (!input) return;
    const atual = parseInt(input.value, 10) || 0;
    const novo = Math.max(0, atual + delta);
    input.value = novo;
    atualizarTotalClientes();
    salvarEstadoPersistido();
}

function zerarClientes() {
    ['inputMono', 'inputBi', 'inputTri'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = 0;
    });
    atualizarTotalClientes();
    salvarEstadoPersistido();
}

function atualizarTotalClientes() {
    const mono = parseInt(document.getElementById('inputMono')?.value || '0', 10) || 0;
    const bi = parseInt(document.getElementById('inputBi')?.value || '0', 10) || 0;
    const tri = parseInt(document.getElementById('inputTri')?.value || '0', 10) || 0;
    const total = mono + bi + tri;
    const lbl = document.getElementById('lblTotalClientes');
    if (lbl) lbl.textContent = total;
    return total;
}

function limparFormulario() {
    const numInput = document.getElementById('inputNumero');
    if (numInput) numInput.value = '01';
    const selPoste = document.getElementById('selectTipoPoste');
    if (selPoste) selPoste.value = '11/600';

    AppState.estruturasMt = [];
    AppState.estruturasBt = ['S1'];
    renderizarTagsEstruturas();

    document.querySelectorAll('#equipChips .chip').forEach(c => c.classList.remove('selected'));
    setTrafoAtivo(false);
    zerarClientes();

    const inputKva = document.getElementById('inputKva');
    const inputKw = document.getElementById('inputKw');
    if (inputKva) inputKva.value = '';
    if (inputKw) inputKw.value = '';

    salvarEstadoPersistido();
    showToast('Formulário limpo com sucesso.', 'info');
}

// Vincula ao window para uso seguro nos handlers HTML onclick
window.alterarCliente = alterarCliente;
window.zerarClientes = zerarClientes;
window.atualizarTotalClientes = atualizarTotalClientes;
window.limparFormulario = limparFormulario;

// Configuração de Formulários e Chips
function setupForms() {
    // Ação: Apagar Marcador
    document.getElementById('btnApagarMarcador')?.addEventListener('click', apagarMarcador);

    // Ação: Limpar Formulário
    document.getElementById('btnLimparForm')?.addEventListener('click', limparFormulario);

    // Ação: Modo Traçado
    document.getElementById('btnToggleTracado')?.addEventListener('click', () => {
        if (window.toggleModoTracado) window.toggleModoTracado();
    });

    // Ação: Ferramenta de Régua / Medição
    document.getElementById('btnToggleMedicao')?.addEventListener('click', () => {
        if (window.toggleModoMedicao) window.toggleModoMedicao(AppState.map);
    });

    // Ação: Restrições Ambientais
    document.getElementById('btnToggleAmbiental')?.addEventListener('click', () => {
        if (window.toggleCamadaAmbiental) window.toggleCamadaAmbiental(AppState.map);
    });

    // Ação: Vias e Obstruções
    document.getElementById('btnToggleVias')?.addEventListener('click', () => {
        if (window.toggleViasObstrucoes) window.toggleViasObstrucoes(AppState.map);
    });

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

    // Eventos de Estruturas MT
    document.getElementById('btnAddMt')?.addEventListener('click', () => {
        const sel = document.getElementById('selectEstruturaMt');
        if (sel && sel.value) {
            adicionarEstruturaMt(sel.value);
            sel.value = '';
        }
    });

    document.getElementById('selectEstruturaMt')?.addEventListener('change', (e) => {
        if (e.target.value) {
            adicionarEstruturaMt(e.target.value);
            e.target.value = '';
        }
    });

    document.querySelectorAll('#quickChipsMt .chip-quick-add').forEach(chip => {
        chip.addEventListener('click', () => {
            adicionarEstruturaMt(chip.getAttribute('data-val'));
        });
    });

    // Eventos de Estruturas BT
    document.getElementById('btnAddBt')?.addEventListener('click', () => {
        const sel = document.getElementById('selectEstruturaBt');
        if (sel && sel.value) {
            adicionarEstruturaBt(sel.value);
            sel.value = '';
        }
    });

    document.getElementById('selectEstruturaBt')?.addEventListener('change', (e) => {
        if (e.target.value) {
            adicionarEstruturaBt(e.target.value);
            e.target.value = '';
        }
    });

    document.querySelectorAll('#quickChipsBt .chip-quick-add').forEach(chip => {
        chip.addEventListener('click', () => {
            adicionarEstruturaBt(chip.getAttribute('data-val'));
        });
    });

    // Chips de Equipamentos (Multi-seleção) e Trafo
    document.querySelectorAll('#equipChips .chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if (chip.id === 'chipTrafo') {
                setTrafoAtivo(!AppState.temTrafo);
            } else {
                chip.classList.toggle('selected');
                salvarEstadoPersistido();
            }
        });
    });

    // Controle de Potência do Trafo
    document.getElementById('selectPotenciaTrafo')?.addEventListener('change', (e) => {
        const val = e.target.value;
        const customInput = document.getElementById('inputPotenciaCustom');
        if (val === 'OUTRO') {
            if (customInput) {
                customInput.style.display = 'block';
                customInput.focus();
                AppState.potenciaTrafo = customInput.value.trim() || '45kVA';
            }
        } else {
            if (customInput) customInput.style.display = 'none';
            AppState.potenciaTrafo = val;
        }
        atualizarLabelTrafo();
        salvarEstadoPersistido();
    });

    document.getElementById('inputPotenciaCustom')?.addEventListener('input', (e) => {
        AppState.potenciaTrafo = e.target.value.trim() || '45kVA';
        atualizarLabelTrafo();
        salvarEstadoPersistido();
    });

    // Persistência automática em inputs
    ['inputNumero', 'selectTipoPoste', 'chkAutoInc'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', salvarEstadoPersistido);
            if (el.tagName === 'INPUT') el.addEventListener('input', salvarEstadoPersistido);
        }
    });

    // Listeners e Sincronização de Consumidores BT (CQT)
    ['inputMono', 'inputBi', 'inputTri'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                atualizarTotalClientes();
                salvarEstadoPersistido();
            });
            el.addEventListener('change', () => {
                const val = parseInt(el.value, 10);
                if (isNaN(val) || val < 0) el.value = 0;
                atualizarTotalClientes();
                salvarEstadoPersistido();
            });
        }
    });

    // Restauração de Consumidores BT do Estado Salvo
    const estadoSalvo = carregarEstadoPersistido();
    if (estadoSalvo) {
        if (estadoSalvo.mono !== undefined && document.getElementById('inputMono')) {
            document.getElementById('inputMono').value = estadoSalvo.mono;
        }
        if (estadoSalvo.bi !== undefined && document.getElementById('inputBi')) {
            document.getElementById('inputBi').value = estadoSalvo.bi;
        }
        if (estadoSalvo.tri !== undefined && document.getElementById('inputTri')) {
            document.getElementById('inputTri').value = estadoSalvo.tri;
        }
        atualizarTotalClientes();
    }

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
    const fuso = parseInt(document.getElementById('selectFuso').value, 10) || 23;

    // Equipamentos selecionados
    const equipamentos = [];
    document.querySelectorAll('#equipChips .chip.selected').forEach(c => {
        const val = c.getAttribute('data-val');
        if (val === 'TRAFO') {
            equipamentos.push(`TRAFO ${AppState.potenciaTrafo}`);
        } else {
            equipamentos.push(val);
        }
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
        estruturaMt: AppState.estruturasMt.join(' / '),
        estruturaBt: AppState.estruturasBt.join(' / '),
        estruturasMt: AppState.estruturasMt,
        estruturasBt: AppState.estruturasBt,
        equipamentos,
        cargaTri,
        fusoUtm: fuso,
        temTrafo: AppState.temTrafo,
        potenciaTrafo: AppState.potenciaTrafo
    };

    enviarParaCSharp(payload);
    showToast(`Enviando poste ${numero} para o AutoCAD...`, 'info');

    // Registrar no traçado contínuo se o modo estiver ativo
    if (window.TracadoState && window.TracadoState.ativo && typeof window.registrarPosteTracado === 'function') {
        window.registrarPosteTracado({
            numero,
            x,
            y,
            lat: AppState.currentLat,
            lon: AppState.currentLon,
            tipoPoste,
            temTrafo: AppState.temTrafo,
            potenciaTrafo: AppState.potenciaTrafo,
            mono: parseInt(document.getElementById('inputMono')?.value || '0', 10) || 0,
            bi: parseInt(document.getElementById('inputBi')?.value || '0', 10) || 0,
            tri: parseInt(document.getElementById('inputTri')?.value || '0', 10) || 0,
            cargaTriKva: parseFloat(document.getElementById('inputKva')?.value || '0') || 0,
            ip70: (document.querySelector('#equipChips .chip[data-val="IP"]')?.classList.contains('selected')) ? 1 : 0
        }, AppState.map);
    }

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
            else if (data.action === 'poligonos_ambientais') {
                if (typeof window.carregarPoligonosAmbientais === 'function') {
                    window.carregarPoligonosAmbientais(data.poligonos || [], AppState.map);
                    if (typeof window.auditarPontoAmbiental === 'function' && AppState.currentLat && AppState.currentLon) {
                        window.auditarPontoAmbiental(AppState.currentLat, AppState.currentLon);
                    }
                }
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

    // Atalhos de teclado (ESC cancela/conclui régua, M ativa régua)
    window.addEventListener('keydown', (e) => {
        const focoEmTexto = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName);
        if (e.key === 'Escape') {
            if (window.MedicaoState?.ativo && typeof window.toggleModoMedicao === 'function') {
                window.toggleModoMedicao(AppState.map);
            }
        } else if ((e.key === 'm' || e.key === 'M') && !focoEmTexto) {
            if (typeof window.toggleModoMedicao === 'function') {
                window.toggleModoMedicao(AppState.map);
            }
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z') && !focoEmTexto) {
            if (window.TracadoState && window.TracadoState.ativo && typeof window.desfazerUltimoPoste === 'function') {
                e.preventDefault();
                window.desfazerUltimoPoste(AppState.map);
            }
        }
    });
});
