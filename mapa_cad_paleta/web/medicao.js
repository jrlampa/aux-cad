/**
 * medicao.js - Ferramenta de Régua e Medição Métrica / Geodésica
 * Permite medir distâncias e vãos livres no mapa com precisão métrica UTM antes de implantar postes.
 */

const MedicaoState = {
    ativo: false,
    pontos: [], // [{ lat, lon, x, y, distParcial, distAcumulada }]
    polylineLayer: null,
    rubberbandLine: null,
    markersLayer: null,
    tooltipMovel: null,
    ultimoPontoHover: null
};

/**
 * Alterna o modo régua / medição
 */
function toggleModoMedicao(mapa) {
    MedicaoState.ativo = !MedicaoState.ativo;
    const btn = document.getElementById('btnToggleMedicao');
    const painel = document.getElementById('painelMedicao');
    const mapDiv = document.getElementById('map');

    if (MedicaoState.ativo) {
        if (btn) {
            btn.classList.add('active');
            btn.innerHTML = '📏 Régua: ATIVA';
        }
        if (painel) painel.style.display = 'block';
        if (mapDiv) mapDiv.classList.add('cursor-crosshair');

        inicializarCamadasMedicao(mapa);
        atualizarPainelMedicao(0, 0, 0);

        if (typeof showToast === 'function') {
            showToast('Régua ativada: Clique no mapa para iniciar a medição (ESC para sair).', 'info');
        }
    } else {
        if (btn) {
            btn.classList.remove('active');
            btn.innerHTML = '📏 Régua';
        }
        if (painel) painel.style.display = 'none';
        if (mapDiv) mapDiv.classList.remove('cursor-crosshair');

        removerRubberband(mapa);
        if (window.SnapMagnetico && typeof window.SnapMagnetico.limparIndicador === 'function') {
            window.SnapMagnetico.limparIndicador(mapa);
        }
    }
}

/**
 * Inicializa as camadas do Leaflet para desenho da medição
 */
function inicializarCamadasMedicao(mapa) {
    if (!mapa) return;
    if (!MedicaoState.polylineLayer) {
        MedicaoState.polylineLayer = L.layerGroup().addTo(mapa);
    }
    if (!MedicaoState.markersLayer) {
        MedicaoState.markersLayer = L.layerGroup().addTo(mapa);
    }
}

/**
 * Registra um clique no mapa durante o modo medição
 */
function cliqueMapaMedicao(e, mapa) {
    if (!MedicaoState.ativo || !mapa) return;

    let lat = e.latlng.lat;
    let lon = e.latlng.lng;

    // Aplica snap magnético aos postes se disponível
    if (window.SnapMagnetico && typeof window.SnapMagnetico.buscarPontoSnap === 'function') {
        const snap = window.SnapMagnetico.buscarPontoSnap(e.latlng, mapa);
        if (snap.snapped) {
            lat = snap.lat;
            lon = snap.lon;
        }
    }

    // Converte para coordenadas métricas UTM
    const fuso = (window.AppState && window.AppState.fusoUtm) ? window.AppState.fusoUtm : 23;
    let x = 0, y = 0;
    if (window.Snyder && typeof window.Snyder.latLonToUtm === 'function') {
        const utm = window.Snyder.latLonToUtm(lat, lon, fuso);
        x = utm.x;
        y = utm.y;
    }

    const n = MedicaoState.pontos.length;
    let distParcial = 0;
    let distAcumulada = 0;

    if (n > 0) {
        const anterior = MedicaoState.pontos[n - 1];
        distParcial = calcularDistanciaMetros(anterior, { lat, lon, x, y });
        distAcumulada = anterior.distAcumulada + distParcial;

        // Desenha linha sólida definitiva para este segmento
        const segLinha = L.polyline([[anterior.lat, anterior.lon], [lat, lon]], {
            color: '#f59e0b', // Âmbar de alta visibilidade
            weight: 3.5,
            dashArray: '4, 4',
            opacity: 0.95
        });
        MedicaoState.polylineLayer.addLayer(segLinha);
    }

    const novoPonto = { lat, lon, x, y, distParcial, distAcumulada };
    MedicaoState.pontos.push(novoPonto);

    // Marcador visual no vértice medido
    const labelTexto = n === 0 ? 'P1 (0m)' : `+${distParcial.toFixed(1)}m (${distAcumulada.toFixed(1)}m)`;
    const verticeMarker = L.circleMarker([lat, lon], {
        radius: 5,
        fillColor: '#f59e0b',
        color: '#ffffff',
        weight: 2,
        fillOpacity: 1
    }).bindTooltip(`<b>${labelTexto}</b>`, {
        permanent: true,
        direction: 'top',
        className: 'medicao-vertice-tooltip',
        offset: [0, -6]
    });

    MedicaoState.markersLayer.addLayer(verticeMarker);
    atualizarPainelMedicao(distAcumulada, distParcial, 0);
}

/**
 * Atualiza a linha elástica (rubberband) e o cálculo ao mover o mouse
 */
function mouseMoveMapaMedicao(e, mapa) {
    if (!MedicaoState.ativo || !mapa || MedicaoState.pontos.length === 0) return;

    let lat = e.latlng.lat;
    let lon = e.latlng.lng;

    // Aplica snap magnético aos postes mais próximos
    if (window.SnapMagnetico && typeof window.SnapMagnetico.buscarPontoSnap === 'function') {
        const snap = window.SnapMagnetico.buscarPontoSnap(e.latlng, mapa);
        if (snap.snapped) {
            lat = snap.lat;
            lon = snap.lon;
        }
    }

    MedicaoState.ultimoPontoHover = { lat, lon };

    const ultimoPonto = MedicaoState.pontos[MedicaoState.pontos.length - 1];
    const distHover = calcularDistanciaMetros(ultimoPonto, { lat, lon });
    const distTotalEstimada = ultimoPonto.distAcumulada + distHover;
    const azimute = calcularAzimuteGraus(ultimoPonto.lat, ultimoPonto.lon, lat, lon);

    // Atualiza ou cria a linha temporária
    if (!MedicaoState.rubberbandLine) {
        MedicaoState.rubberbandLine = L.polyline([[ultimoPonto.lat, ultimoPonto.lon], [lat, lon]], {
            color: '#fbbf24',
            weight: 2.5,
            dashArray: '3, 5',
            opacity: 0.75
        }).addTo(mapa);
    } else {
        MedicaoState.rubberbandLine.setLatLngs([[ultimoPonto.lat, ultimoPonto.lon], [lat, lon]]);
    }

    atualizarPainelMedicao(distTotalEstimada, distHover, azimute);
}

/**
 * Remove a linha elástica temporária
 */
function removerRubberband(mapa) {
    if (MedicaoState.rubberbandLine && mapa) {
        mapa.removeLayer(MedicaoState.rubberbandLine);
        MedicaoState.rubberbandLine = null;
    }
}

/**
 * Calcula distância métrica entre dois pontos (via UTM ou Haversine analítico)
 */
function calcularDistanciaMetros(p1, p2) {
    if (p1.x && p1.y && p2.x && p2.y) {
        return Math.hypot(p2.x - p1.x, p2.y - p1.y);
    }
    // Haversine analítico de precisão
    const R = 6371000; // Raio médio da Terra em metros
    const dLat = (p2.lat - p1.lat) * (Math.PI / 180);
    const dLon = (p2.lon - p1.lon) * (Math.PI / 180);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(p1.lat * (Math.PI / 180)) * Math.cos(p2.lat * (Math.PI / 180)) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * Calcula o azimute em graus (0° a 360°)
 */
function calcularAzimuteGraus(lat1, lon1, lat2, lon2) {
    const dLon = (lon2 - lon1) * (Math.PI / 180);
    const phi1 = lat1 * (Math.PI / 180);
    const phi2 = lat2 * (Math.PI / 180);
    const y = Math.sin(dLon) * Math.cos(phi2);
    const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLon);
    let brng = Math.atan2(y, x) * (180 / Math.PI);
    return (brng + 360) % 360;
}

/**
 * Atualiza o painel flutuante de medição
 */
function atualizarPainelMedicao(total, parcial, azimute) {
    const elTotal = document.getElementById('txtMedicaoTotal');
    const elParcial = document.getElementById('txtMedicaoParcial');
    const elAzimute = document.getElementById('txtMedicaoAzimute');
    const elPontos = document.getElementById('txtMedicaoPontos');

    if (elTotal) elTotal.textContent = `${total.toFixed(1)} m`;
    if (elParcial) elParcial.textContent = `${parcial.toFixed(1)} m`;
    if (elAzimute) elAzimute.textContent = `${azimute.toFixed(0)}°`;
    if (elPontos) elPontos.textContent = `${MedicaoState.pontos.length} pontos`;
}

/**
 * Inicia a medição a partir da posição atual do poste marcado
 */
function medirAPartirDoPoste(mapa) {
    if (!window.AppState || !window.AppState.hasMarker) {
        if (typeof showToast === 'function') {
            showToast('Nenhum poste posicionado no mapa ainda.', 'warning');
        }
        return;
    }

    limparMedicao(mapa);
    if (!MedicaoState.ativo) {
        toggleModoMedicao(mapa);
    }

    cliqueMapaMedicao({
        latlng: {
            lat: window.AppState.currentLat,
            lng: window.AppState.currentLon
        }
    }, mapa);

    if (typeof showToast === 'function') {
        showToast('Medição iniciada no ponto do poste atual.', 'info');
    }
}

/**
 * Posiciona o marcador de lançamento de poste no último ponto clicado da régua
 */
function posicionarPosteNoUltimoPonto(mapa) {
    const n = MedicaoState.pontos.length;
    let alvo = null;
    if (n > 0) {
        alvo = MedicaoState.pontos[n - 1];
    } else if (MedicaoState.ultimoPontoHover) {
        alvo = MedicaoState.ultimoPontoHover;
    }

    if (!alvo) {
        if (typeof showToast === 'function') {
            showToast('Nenhum ponto medido para posicionar o poste.', 'warning');
        }
        return;
    }

    if (typeof window.posicionarMarcador === 'function') {
        window.posicionarMarcador(alvo.lat, alvo.lon);
        if (typeof showToast === 'function') {
            showToast('Marcador do poste posicionado na coordenada medida!', 'success');
        }
    }
}

/**
 * Limpa todos os pontos e geometrias de medição
 */
function limparMedicao(mapa) {
    MedicaoState.pontos = [];
    MedicaoState.ultimoPontoHover = null;
    if (MedicaoState.polylineLayer && mapa) {
        MedicaoState.polylineLayer.clearLayers();
    }
    if (MedicaoState.markersLayer && mapa) {
        MedicaoState.markersLayer.clearLayers();
    }
    removerRubberband(mapa);
    atualizarPainelMedicao(0, 0, 0);
}

// Exportação global
window.MedicaoState = MedicaoState;
window.toggleModoMedicao = toggleModoMedicao;
window.cliqueMapaMedicao = cliqueMapaMedicao;
window.mouseMoveMapaMedicao = mouseMoveMapaMedicao;
window.medirAPartirDoPoste = medirAPartirDoPoste;
window.posicionarPosteNoUltimoPonto = posicionarPosteNoUltimoPonto;
window.limparMedicao = limparMedicao;
