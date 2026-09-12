/**
 * tracado.js - Módulo de Traçado Contínuo de Linhas / Vãos de Rede
 * Desenha polilinhas de cabos entre postes sequenciais e envia comandos de desenho 2.5D ao AutoCAD.
 */

const TracadoState = {
    ativo: false,
    tipoRede: 'BT', // 'BT' ou 'MT'
    pontos: [],     // [{ numero, x, y, lat, lon }]
    polylineLayer: null,
    labelsLayer: null
};

/**
 * Alterna o Modo Traçado Contínuo
 */
function toggleModoTracado(forcarEstado = null) {
    TracadoState.ativo = forcarEstado !== null ? forcarEstado : !TracadoState.ativo;
    
    const btn = document.getElementById('btnToggleTracado');
    const painel = document.getElementById('painelTracado');
    
    if (btn) {
        if (TracadoState.ativo) {
            btn.classList.add('active');
            btn.innerHTML = '📐 Traçado: ATIVO';
            btn.title = 'Modo Traçado ATIVO: Novos postes conectarão vãos automaticamente no CAD';
        } else {
            btn.classList.remove('active');
            btn.innerHTML = '📐 Modo Traçado';
            btn.title = 'Ativar modo traçado contínuo de rede';
        }
    }
    
    if (painel) {
        painel.style.display = TracadoState.ativo ? 'block' : 'none';
    }
    
    atualizarInfoTracado();
}

/**
 * Define o tipo de rede para o traçado ('BT' ou 'MT')
 */
function setTipoRedeTracado(tipo) {
    TracadoState.tipoRede = (tipo === 'MT') ? 'MT' : 'BT';
    const btnBt = document.getElementById('btnRedeBt');
    const btnMt = document.getElementById('btnRedeMt');
    if (btnBt && btnMt) {
        if (TracadoState.tipoRede === 'BT') {
            btnBt.classList.add('active');
            btnMt.classList.remove('active');
        } else {
            btnBt.classList.remove('active');
            btnMt.classList.add('active');
        }
    }
}

/**
 * Registra um poste no traçado e, se houver anterior, dispara a inserção do vão no CAD
 */
function registrarPosteTracado(novoPoste, mapa) {
    if (!TracadoState.ativo || !novoPoste) return;

    const anterior = TracadoState.pontos.length > 0 
        ? TracadoState.pontos[TracadoState.pontos.length - 1] 
        : null;

    TracadoState.pontos.push(novoPoste);

    // Carrega e renderiza vias, calçadas e obstruções no entorno do novo poste
    if (typeof window.carregarContextoUrbano === 'function' && novoPoste.lat && novoPoste.lon) {
        window.carregarContextoUrbano(novoPoste.lat, novoPoste.lon, 100, mapa);
    }

    if (anterior && mapa) {
        // Cálculo analítico de distância no plano métrico UTM
        const dx = novoPoste.x - anterior.x;
        const dy = novoPoste.y - anterior.y;
        const distMetros = Math.hypot(dx, dy);

        // Desenha visualmente o vão no Leaflet
        desenharVaoNoMapa(anterior, novoPoste, distMetros, mapa);

        // Envia mensagem ao AutoCAD via C# Bridge
        if (window.chrome && window.chrome.webview) {
            window.chrome.webview.postMessage({
                action: 'desenhar_vao',
                x1: anterior.x,
                y1: anterior.y,
                x2: novoPoste.x,
                y2: novoPoste.y,
                tipoRede: TracadoState.tipoRede,
                textoVao: `${distMetros.toFixed(1)}m`,
                numDe: anterior.numero,
                numPara: novoPoste.numero
            });
        }
    }

    atualizarInfoTracado();
}

/**
 * Desenha a polilinha e a etiqueta de comprimento no Leaflet
 */
function desenharVaoNoMapa(p1, p2, distMetros, mapa) {
    if (!mapa) return;

    if (!TracadoState.polylineLayer) {
        TracadoState.polylineLayer = L.layerGroup().addTo(mapa);
    }
    if (!TracadoState.labelsLayer) {
        TracadoState.labelsLayer = L.layerGroup().addTo(mapa);
    }

    const corLinha = TracadoState.tipoRede === 'MT' ? '#800080' : '#00b4d8'; // Roxo para MT, Ciano para BT
    const linha = L.polyline([[p1.lat, p1.lon], [p2.lat, p2.lon]], {
        color: corLinha,
        weight: 3,
        dashArray: '6, 4',
        opacity: 0.85
    });
    TracadoState.polylineLayer.addLayer(linha);

    // Rótulo no ponto médio
    const midLat = (p1.lat + p2.lat) / 2;
    const midLon = (p1.lon + p2.lon) / 2;
    const labelMarker = L.marker([midLat, midLon], {
        icon: L.divIcon({
            className: 'vao-distance-label',
            html: `<span>${distMetros.toFixed(1)}m</span>`,
            iconSize: [60, 20],
            iconAnchor: [30, 10]
        })
    });
    TracadoState.labelsLayer.addLayer(labelMarker);
}

/**
 * Atualiza o indicador textual do traçado na barra lateral
 */
function atualizarInfoTracado() {
    const lblContagem = document.getElementById('lblTracadoContagem');
    const lblUltimo = document.getElementById('lblTracadoUltimo');
    
    const count = TracadoState.pontos.length;
    if (lblContagem) {
        lblContagem.textContent = `${count} ${count === 1 ? 'poste' : 'postes'}`;
    }
    if (lblUltimo) {
        if (count > 0) {
            const ult = TracadoState.pontos[count - 1];
            lblUltimo.textContent = `Último: P${ult.numero}`;
        } else {
            lblUltimo.textContent = 'Nenhum poste no traçado';
        }
    }
}

/**
 * Reinicia o traçado atual (limpa linhas no mapa e histórico)
 */
function limparTracado(mapa) {
    TracadoState.pontos = [];
    if (TracadoState.polylineLayer && mapa) {
        mapa.removeLayer(TracadoState.polylineLayer);
        TracadoState.polylineLayer = null;
    }
    if (TracadoState.labelsLayer && mapa) {
        mapa.removeLayer(TracadoState.labelsLayer);
        TracadoState.labelsLayer = null;
    }
    atualizarInfoTracado();
}

/**
 * Conclui o trecho atual, permitindo iniciar um novo ramal sem apagar o desenho
 */
function finalizarTrecho() {
    TracadoState.pontos = [];
    atualizarInfoTracado();
}

// Exporta para escopo global
window.TracadoState = TracadoState;
window.toggleModoTracado = toggleModoTracado;
window.setTipoRedeTracado = setTipoRedeTracado;
window.registrarPosteTracado = registrarPosteTracado;
window.limparTracado = limparTracado;
window.finalizarTrecho = finalizarTrecho;
