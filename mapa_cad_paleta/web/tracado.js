/**
 * tracado.js - Módulo de Traçado Contínuo de Linhas / Vãos de Rede
 * Desenha polilinhas de cabos entre postes sequenciais e envia comandos de desenho 2.5D ao AutoCAD.
 */

const TracadoState = {
    ativo: false,
    tipoRede: 'BT', // 'BT' ou 'MT'
    pontos: [],     // [{ numero, x, y, lat, lon, tipoPoste, temTrafo, potenciaTrafo, mono, bi, tri, cargaTriKva, ip70 }]
    polylineLayer: null,
    labelsLayer: null,
    markersLayer: null,
    listaAberta: false
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
    // Redesenha com a nova cor da rede selecionada
    const mapa = (window.AppState && window.AppState.map) ? window.AppState.map : null;
    if (mapa && TracadoState.pontos.length > 0) {
        redesenharTodoTracado(mapa);
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

    // Carrega e renderiza vias, calçadas e obstruções no entorno do novo poste e ao longo do vão
    const chkViasTracado = document.getElementById('chkTracadoViasCad') || document.getElementById('chkAutoViasCad');
    const desenharVias = chkViasTracado ? chkViasTracado.checked : (window.ViasObstrucoesState && window.ViasObstrucoesState.desenharNoCad);

    if (desenharVias && typeof window.carregarContextoUrbano === 'function' && novoPoste.lat && novoPoste.lon) {
        if (window.ViasObstrucoesState) window.ViasObstrucoesState.desenharNoCad = true;
        window.carregarContextoUrbano(novoPoste.lat, novoPoste.lon, 120, mapa);

        // Cobre também o ponto médio do vão para capturar a extensão completa da via no AutoCAD
        if (anterior && anterior.lat && anterior.lon) {
            const midLat = (anterior.lat + novoPoste.lat) / 2.0;
            const midLon = (anterior.lon + novoPoste.lon) / 2.0;
            const distVao = Math.hypot(novoPoste.x - anterior.x, novoPoste.y - anterior.y);
            const raioVao = Math.max(100, Math.min(250, distVao / 1.5));
            window.carregarContextoUrbano(midLat, midLon, raioVao, mapa);
        }
    }

    if (anterior && mapa) {
        // Cálculo analítico de distância no plano métrico UTM
        const dx = novoPoste.x - anterior.x;
        const dy = novoPoste.y - anterior.y;
        const distMetros = Math.hypot(dx, dy);

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

    // Reconstrói todo o traçado garantindo marcadores interativos para cada poste
    redesenharTodoTracado(mapa);
}

/**
 * Cria o marcador visual interativo e arrastável para um poste do traçado
 */
function criarMarcadorPosteTracado(p, idx, mapa) {
    const isMt = TracadoState.tipoRede === 'MT';
    const bgCor = isMt ? '#00e5ff' : '#ffd600';
    const borderCor = isMt ? '#0891b2' : '#ca8a04';
    const txtCor = '#0f172a';

    const customIcon = L.divIcon({
        className: 'tracado-node-marker',
        html: `
            <div style="
                background: ${bgCor};
                border: 2px solid ${borderCor};
                color: ${txtCor};
                width: 28px;
                height: 28px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                font-weight: 800;
                box-shadow: 0 2px 6px rgba(0,0,0,0.4);
                cursor: grab;
                user-select: none;
            " title="Poste P${p.numero} - Arraste para mover ou clique com botão direito para remover">
                P${p.numero}
            </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
    });

    const marker = L.marker([p.lat, p.lon], {
        draggable: true,
        icon: customIcon,
        zIndexOffset: 1000 + idx
    });

    // Evento de Arraste (Drag & Drop): Move poste e recalcula todos os vãos em tempo real
    marker.on('dragend', (e) => {
        const novaPos = e.target.getLatLng();
        const fuso = (window.AppState && window.AppState.fuso) ? window.AppState.fuso : 23;

        let novoX = p.x;
        let novoY = p.y;
        if (window.Snyder && typeof window.Snyder.latLonToUtm === 'function') {
            const utm = window.Snyder.latLonToUtm(novaPos.lat, novaPos.lng, fuso);
            novoX = utm.x;
            novoY = utm.y;
        }

        p.lat = novaPos.lat;
        p.lon = novaPos.lng;
        p.x = novoX;
        p.y = novoY;

        redesenharTodoTracado(mapa);

        if (typeof showToast === 'function') {
            showToast(`📍 Poste P${p.numero} reposicionado (X: ${novoX.toFixed(1)}, Y: ${novoY.toFixed(1)}). Vãos recalculados!`, 'success');
        }
    });

    // Clique no marcador: Popup informativo e com opções de ação
    const popupContent = `
        <div style="font-family: sans-serif; font-size: 11px; min-width: 170px;">
            <div style="font-weight: bold; color: #1e293b; margin-bottom: 4px; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px;">
                ⚡ Poste P${p.numero} (${TracadoState.tipoRede})
            </div>
            <div style="color: #64748b; margin-bottom: 6px;">
                X: <strong>${p.x.toFixed(2)}</strong><br>
                Y: <strong>${p.y.toFixed(2)}</strong>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                <button type="button" onclick="focarPosteNaSidebar(${idx})" style="background: #0284c7; color: white; border: none; padding: 4px; border-radius: 3px; font-size: 10px; cursor: pointer; font-weight: 600;">
                    📍 Carregar na Sidebar
                </button>
                <button type="button" onclick="removerPosteTracado(${idx}, window.AppState ? window.AppState.map : null)" style="background: #ef4444; color: white; border: none; padding: 4px; border-radius: 3px; font-size: 10px; cursor: pointer; font-weight: 600;">
                    🗑️ Remover do Traçado
                </button>
            </div>
        </div>
    `;
    marker.bindPopup(popupContent);

    // Clique com botão direito no marcador: atalho rápido de exclusão
    marker.on('contextmenu', (e) => {
        L.DomEvent.stopPropagation(e);
        removerPosteTracado(idx, mapa);
    });

    return marker;
}

/**
 * Foca o poste selecionado e carrega suas coordenadas na sidebar
 */
function focarPosteNaSidebar(idx) {
    if (idx < 0 || idx >= TracadoState.pontos.length) return;
    const p = TracadoState.pontos[idx];
    if (typeof window.posicionarMarcador === 'function') {
        window.posicionarMarcador(p.lat, p.lon);
    }
    const inpX = document.getElementById('inputX');
    const inpY = document.getElementById('inputY');
    if (inpX && inpY) {
        inpX.value = p.x.toFixed(2);
        inpY.value = p.y.toFixed(2);
    }
    if (typeof showToast === 'function') {
        showToast(`Coordenadas do Poste P${p.numero} carregadas na sidebar.`, 'info');
    }
}
window.focarPosteNaSidebar = focarPosteNaSidebar;

/**
 * Desfaz o último poste inserido no traçado (reverte 1 passo)
 */
function desfazerUltimoPoste(mapa) {
    if (!TracadoState.pontos || TracadoState.pontos.length === 0) {
        if (typeof showToast === 'function') {
            showToast('Nenhum poste no traçado para desfazer.', 'warning');
        }
        return;
    }

    const mapaAlvo = mapa || (window.AppState ? window.AppState.map : null);
    const removido = TracadoState.pontos.pop();
    redesenharTodoTracado(mapaAlvo);

    // Notifica C# / AutoCAD para remover o último vão desenhado
    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage({
            action: 'desfazer_vao',
            numero: removido.numero
        });
    }

    if (typeof showToast === 'function') {
        showToast(`↩️ Poste P${removido.numero} removido do traçado.`, 'info');
    }
}

/**
 * Remove um poste específico do traçado por índice e reconecta os vãos adjacentes
 */
function removerPosteTracado(idx, mapa) {
    if (idx < 0 || idx >= TracadoState.pontos.length) return;

    const mapaAlvo = mapa || (window.AppState ? window.AppState.map : null);
    const removido = TracadoState.pontos.splice(idx, 1)[0];
    redesenharTodoTracado(mapaAlvo);

    if (typeof showToast === 'function') {
        showToast(`🗑️ Poste P${removido.numero} excluído do traçado. Vãos reconectados!`, 'info');
    }
}

/**
 * Reconstrói e redesenha visualmente todo o traçado (polilinhas, rótulos e marcadores arrastáveis)
 */
function redesenharTodoTracado(mapa) {
    const mapaAlvo = mapa || (window.AppState ? window.AppState.map : null);
    if (!mapaAlvo) return;

    // Inicializa ou limpa as camadas no mapa
    if (!TracadoState.polylineLayer) {
        TracadoState.polylineLayer = L.layerGroup().addTo(mapaAlvo);
    } else {
        TracadoState.polylineLayer.clearLayers();
    }

    if (!TracadoState.labelsLayer) {
        TracadoState.labelsLayer = L.layerGroup().addTo(mapaAlvo);
    } else {
        TracadoState.labelsLayer.clearLayers();
    }

    if (!TracadoState.markersLayer) {
        TracadoState.markersLayer = L.layerGroup().addTo(mapaAlvo);
    } else {
        TracadoState.markersLayer.clearLayers();
    }

    // Desenha cada poste e cada vão sequencial
    for (let i = 0; i < TracadoState.pontos.length; i++) {
        const p = TracadoState.pontos[i];

        // Cria marcador interativo e arrastável
        const m = criarMarcadorPosteTracado(p, i, mapaAlvo);
        TracadoState.markersLayer.addLayer(m);

        // Desenha vão conectando ao poste anterior
        if (i > 0) {
            const anterior = TracadoState.pontos[i - 1];
            const dx = p.x - anterior.x;
            const dy = p.y - anterior.y;
            const dist = Math.hypot(dx, dy);
            desenharVaoNoMapa(anterior, p, dist, mapaAlvo);
        }
    }

    atualizarInfoTracado();
    renderizarListaPostesTracado();
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
        weight: 3.5,
        dashArray: '6, 4',
        opacity: 0.9
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
 * Alterna a visibilidade do painel de lista detalhada de postes
 */
function toggleListaPostes() {
    TracadoState.listaAberta = !TracadoState.listaAberta;
    const pnl = document.getElementById('painelListaPostes');
    if (pnl) {
        pnl.style.display = TracadoState.listaAberta ? 'block' : 'none';
        if (TracadoState.listaAberta) {
            renderizarListaPostesTracado();
        }
    }
}
window.toggleListaPostes = toggleListaPostes;

/**
 * Renderiza os itens na lista de postes do traçado
 */
function renderizarListaPostesTracado() {
    const container = document.getElementById('containerItensPostes');
    if (!container) return;

    if (!TracadoState.pontos || TracadoState.pontos.length === 0) {
        container.innerHTML = '<div style="color: #94a3b8; font-style: italic; padding: 4px 0;">Nenhum poste adicionado ao traçado.</div>';
        return;
    }

    container.innerHTML = TracadoState.pontos.map((p, idx) => {
        let infoVao = '';
        if (idx > 0) {
            const ant = TracadoState.pontos[idx - 1];
            const dist = Math.hypot(p.x - ant.x, p.y - ant.y);
            infoVao = `<span class="badge-vao-dist">${dist.toFixed(1)}m</span>`;
        }
        return `
            <div class="tracado-poste-row">
                <div class="tracado-poste-info">
                    <span class="tracado-num-badge">P${p.numero}</span>
                    ${infoVao}
                    <span class="tracado-coords-sm">X:${Math.round(p.x)} Y:${Math.round(p.y)}</span>
                </div>
                <div class="tracado-row-actions">
                    <button type="button" class="btn-icon-row" onclick="focarPosteNoMapa(${idx})" title="Focar e centralizar no mapa">👁️</button>
                    <button type="button" class="btn-icon-row danger" onclick="removerPosteTracado(${idx})" title="Excluir este poste do traçado">🗑️</button>
                </div>
            </div>
        `;
    }).join('');
}
window.renderizarListaPostesTracado = renderizarListaPostesTracado;

/**
 * Centraliza o mapa no poste especificado
 */
function focarPosteNoMapa(idx) {
    if (idx < 0 || idx >= TracadoState.pontos.length) return;
    const p = TracadoState.pontos[idx];
    const mapa = (window.AppState && window.AppState.map) ? window.AppState.map : null;
    if (mapa) {
        mapa.flyTo([p.lat, p.lon], 19);
    }
}
window.focarPosteNoMapa = focarPosteNoMapa;

/**
 * Reinicia o traçado atual (limpa linhas no mapa e histórico)
 */
function limparTracado(mapa) {
    const mapaAlvo = mapa || (window.AppState ? window.AppState.map : null);
    TracadoState.pontos = [];
    if (TracadoState.polylineLayer && mapaAlvo) {
        mapaAlvo.removeLayer(TracadoState.polylineLayer);
        TracadoState.polylineLayer = null;
    }
    if (TracadoState.labelsLayer && mapaAlvo) {
        mapaAlvo.removeLayer(TracadoState.labelsLayer);
        TracadoState.labelsLayer = null;
    }
    if (TracadoState.markersLayer && mapaAlvo) {
        mapaAlvo.removeLayer(TracadoState.markersLayer);
        TracadoState.markersLayer = null;
    }
    atualizarInfoTracado();
    renderizarListaPostesTracado();
}

/**
 * Conclui o trecho atual, permitindo iniciar um novo ramal sem apagar o desenho
 */
function finalizarTrecho() {
    TracadoState.pontos = [];
    atualizarInfoTracado();
    renderizarListaPostesTracado();
}

/**
 * Exporta os trechos e postes do traçado diretamente para o módulo CQT (Queda de Tensão)
 * Se houver 2 ou mais postes: transfere os vãos, condutores e clientes Mono/Bi/Tri calculados.
 * Se não houver traçado ativo: abre a CQTUI para estudo prévio com dados do formulário/trafo.
 */
function exportarParaCqt() {
    const letras = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"];
    const inputProj = document.getElementById('inputProjeto');
    const nomeProj = (inputProj && inputProj.value.trim()) ? inputProj.value.trim() : 'PE_OSM_TRAÇADO';

    const inputMono = document.getElementById('inputMono');
    const inputBi = document.getElementById('inputBi');
    const inputTri = document.getElementById('inputTri');
    const cliMono = inputMono ? parseInt(inputMono.value) || 0 : 0;
    const cliBi = inputBi ? parseInt(inputBi.value) || 0 : 0;
    const cliTri = inputTri ? parseInt(inputTri.value) || 0 : 0;

    let pontoTrafoNome = 'P01';
    let potTrafoStr = '45';

    const temPontos = TracadoState.pontos && TracadoState.pontos.length >= 1;
    const temVaos = TracadoState.pontos && TracadoState.pontos.length >= 2;

    if (temPontos) {
        let posteTrafo = TracadoState.pontos.find(p => p.temTrafo || (p.potenciaTrafo && p.potenciaTrafo !== ''));
        if (!posteTrafo) {
            posteTrafo = TracadoState.pontos[0];
        }
        pontoTrafoNome = posteTrafo.numero ? `P${posteTrafo.numero}` : 'P01';
        potTrafoStr = (posteTrafo.potenciaTrafo || '45kVA').replace(/[^0-9.]/g, '') || '45';
    } else {
        const inputNum = document.getElementById('inputNumeroPoste');
        if (inputNum && inputNum.value.trim()) pontoTrafoNome = `P${inputNum.value.trim()}`;
        const selTrafo = document.getElementById('selectTrafo');
        if (selTrafo && selTrafo.value) potTrafoStr = selTrafo.value.replace(/[^0-9.]/g, '') || '45';
    }

    const trechosCqt = [];

    if (temVaos) {
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
    }

    const cqtPayload = {
        projeto: nomeProj,
        ponto_trafo: pontoTrafoNome,
        potencia_trafo: potTrafoStr,
        cenario: 'PROJETADO',
        trechos: trechosCqt,
        consumidores_base: {
            mono: cliMono,
            bi: cliBi,
            tri: cliTri
        }
    };

    // Envio para WebView2 / C# Bridge
    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage({
            action: 'exportar_cqt',
            dadosCqt: cqtPayload
        });
        if (temVaos) {
            if (typeof showToast === 'function') {
                showToast(`⚡ ${trechosCqt.length} vãos exportados! Abrindo CQTUI...`, 'success');
            }
        } else {
            if (typeof showToast === 'function') {
                showToast('⚡ Abrindo Gerenciador CQTUI (estudo prévio)...', 'info');
            }
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
window.desfazerUltimoPoste = desfazerUltimoPoste;
window.removerPosteTracado = removerPosteTracado;
window.redesenharTodoTracado = redesenharTodoTracado;
window.toggleListaPostes = toggleListaPostes;
window.renderizarListaPostesTracado = renderizarListaPostesTracado;
window.focarPosteNoMapa = focarPosteNoMapa;
window.limparTracado = limparTracado;
window.finalizarTrecho = finalizarTrecho;
window.exportarParaCqt = exportarParaCqt;

