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

    const corLinha = TracadoState.tipoRede === 'MT' ? '#00e5ff' : '#ffd600'; // MT: Ciano (Cyan) | BT: Amarelo (Yellow)
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

/**
 * Exporta os trechos e postes do traçado diretamente para o módulo CQT (Queda de Tensão)
 */
function exportarParaCqt() {
    if (!TracadoState.pontos || TracadoState.pontos.length < 2) {
        if (typeof showToast === 'function') {
            showToast('Trace pelo menos 2 postes para gerar vãos para o CQT.', 'warning');
        } else {
            alert('Trace pelo menos 2 postes para gerar vãos para o CQT.');
        }
        return;
    }

    const letras = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"];
    
    // Identifica o poste do trafo (primeiro com trafo ou o primeiro poste do traçado)
    let posteTrafo = TracadoState.pontos.find(p => p.temTrafo || (p.potenciaTrafo && p.potenciaTrafo !== ''));
    if (!posteTrafo) {
        posteTrafo = TracadoState.pontos[0];
    }

    const pontoTrafoNome = posteTrafo.numero ? `P${posteTrafo.numero}` : 'P01';
    let potTrafoStr = posteTrafo.potenciaTrafo || '45kVA';
    potTrafoStr = potTrafoStr.replace(/[^0-9.]/g, '') || '45';

    const trechosCqt = [];

    for (let i = 1; i < TracadoState.pontos.length; i++) {
        const pAnt = TracadoState.pontos[i - 1];
        const pAtual = TracadoState.pontos[i];

        // Distância euclidiana métrica UTM
        const dx = pAtual.x - pAnt.x;
        const dy = pAtual.y - pAnt.y;
        const dist = Math.hypot(dx, dy);

        const letra = (i - 1 < letras.length) ? letras[i - 1] : `T${i}`;
        const montante = (i === 1) ? 'TRAFO' : letras[i - 2];

        // Cabo padrão BT
        const cabo = (i === 1) ? '3x150+70 - Al - F.P 1' : '3x35+1x54,6 - Al - F.P 1';

        trechosCqt.push({
            letra: letra,
            de: `P${pAnt.numero}`,
            para: `P${pAtual.numero}`,
            montante: montante,
            vaos: 1,
            comprimento_m: parseFloat(dist.toFixed(1)),
            condutor: cabo,
            mono: pAtual.mono || 0,
            bi: pAtual.bi || 0,
            tri: pAtual.tri || 0,
            esp_carga: pAtual.cargaTriKva || 0,
            ip70: pAtual.ip70 || 0,
            ip125: pAtual.ip125 || 0,
            ip250: pAtual.ip250 || 0
        });
    }

    const inputProj = document.getElementById('inputProjeto');
    const nomeProj = (inputProj && inputProj.value.trim()) ? inputProj.value.trim() : 'PE_OSM_TRAÇADO';

    const cqtPayload = {
        projeto: nomeProj,
        ponto_trafo: pontoTrafoNome,
        potencia_trafo: potTrafoStr,
        cenario: 'PROJETADO',
        trechos: trechosCqt
    };

    // Envio para WebView2 / C# Bridge
    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage({
            action: 'exportar_cqt',
            dadosCqt: cqtPayload
        });
        if (typeof showToast === 'function') {
            showToast(`⚡ ${trechosCqt.length} vãos exportados para CQT!`, 'success');
        }
    } else {
        // Fallback navegador: download JSON
        const blob = new Blob([JSON.stringify(cqtPayload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `CQT_${nomeProj}.json`;
        a.click();
        URL.revokeObjectURL(url);
        if (typeof showToast === 'function') {
            showToast(`JSON CQT baixado com sucesso! (${trechosCqt.length} vãos)`, 'success');
        }
    }
}

// Exporta para escopo global
window.TracadoState = TracadoState;
window.toggleModoTracado = toggleModoTracado;
window.setTipoRedeTracado = setTipoRedeTracado;
window.registrarPosteTracado = registrarPosteTracado;
window.limparTracado = limparTracado;
window.finalizarTrecho = finalizarTrecho;
window.exportarParaCqt = exportarParaCqt;
