/**
 * ambiental_overlay.js - Camada de Restrições Ambientais e Auditoria em Tempo Real
 * Renderiza polígonos de APPs, UCs e Exclusão no Leaflet e executa Ray-Casting analítico.
 */

const AmbientalState = {
    ativo: false,
    polygonsLayer: null,
    poligonos: [], // [{ nome, categoria, cor, pontos: [[lat, lon], ...] }]
    ultimaIncidencia: null
};

/**
 * Alterna a visualização da camada ambiental no mapa
 */
function toggleCamadaAmbiental(mapa) {
    AmbientalState.ativo = !AmbientalState.ativo;
    const btn = document.getElementById('btnToggleAmbiental');
    
    if (btn) {
        if (AmbientalState.ativo) {
            btn.classList.add('active');
            btn.innerHTML = '🌿 Restrições: VISÍVEIS';
        } else {
            btn.classList.remove('active');
            btn.innerHTML = '🌿 Restrições';
        }
    }

    if (!mapa) return;

    if (AmbientalState.ativo) {
        if (AmbientalState.polygonsLayer) {
            mapa.addLayer(AmbientalState.polygonsLayer);
        } else {
            // Se ainda não carregou polígonos, solicita ao C# abrir KMZ
            solicitarKmzAmbiental();
        }
    } else {
        if (AmbientalState.polygonsLayer) {
            mapa.removeLayer(AmbientalState.polygonsLayer);
        }
    }
}

/**
 * Solicita ao backend C# abrir o diálogo de seleção de arquivo KMZ/KML
 */
function solicitarKmzAmbiental() {
    if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage({ action: 'abrir_kmz_ambiental' });
    }
}

/**
 * Carrega a lista de polígonos no Leaflet e inicializa o cache de auditoria
 */
function carregarPoligonosAmbientais(listaPoligonos, mapa) {
    if (!listaPoligonos || !Array.isArray(listaPoligonos)) return;

    AmbientalState.poligonos = listaPoligonos;

    if (!mapa) return;

    if (AmbientalState.polygonsLayer) {
        mapa.removeLayer(AmbientalState.polygonsLayer);
    }
    AmbientalState.polygonsLayer = L.layerGroup();

    listaPoligonos.forEach(poly => {
        if (!poly.pontos || poly.pontos.length < 3) return;

        let cor = '#f77f00'; // Padrão APP / Amortecimento (Laranja)
        let fillOpacity = 0.25;

        const cat = (poly.categoria || '').toUpperCase();
        if (cat.includes('EXCLUSAO') || cat.includes('RESTRICAO')) {
            cor = '#d90429'; // Vermelho alerta
            fillOpacity = 0.35;
        } else if (cat.includes('UC') || cat.includes('PARQUE')) {
            cor = '#2a9d8f'; // Verde petróleo
            fillOpacity = 0.20;
        } else if (cat.includes('HIDRICA') || cat.includes('RIO') || cat.includes('NASCENTE')) {
            cor = '#0077b6'; // Azul hídrico
            fillOpacity = 0.30;
        }

        const lPoly = L.polygon(poly.pontos, {
            color: cor,
            weight: 2,
            fillColor: cor,
            fillOpacity: fillOpacity
        });

        const rotulo = poly.nome || poly.categoria || 'Restrição Ambiental';
        lPoly.bindTooltip(`<b>${rotulo}</b><br>${poly.categoria || ''}`, {
            sticky: true,
            direction: 'top'
        });

        AmbientalState.polygonsLayer.addLayer(lPoly);
    });

    if (AmbientalState.ativo) {
        mapa.addLayer(AmbientalState.polygonsLayer);
    }

    const btn = document.getElementById('btnToggleAmbiental');
    if (btn) {
        btn.classList.add('active');
        btn.innerHTML = `🌿 Restrições (${listaPoligonos.length})`;
        AmbientalState.ativo = true;
    }

    // Reaudita a posição atual se houver marcador
    if (window.AppState && window.AppState.hasMarker) {
        auditarPontoAmbiental(window.AppState.currentLat, window.AppState.currentLon);
    }
}

/**
 * Algoritmo analítico Ray-Casting para testar se ponto (lat, lon) cai dentro de um polígono
 */
function rayCastingPontoEmPoligono(lat, lon, vs) {
    let inside = false;
    for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
        const xi = vs[i][0], yi = vs[i][1];
        const xj = vs[j][0], yj = vs[j][1];

        const intersect = ((yi > lon) !== (yj > lon)) &&
            (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

/**
 * Audita as coordenadas em tempo real contra todos os polígonos carregados
 */
function auditarPontoAmbiental(lat, lon) {
    const banner = document.getElementById('bannerAmbiental');
    if (!banner) return;

    if (!AmbientalState.poligonos || AmbientalState.poligonos.length === 0) {
        banner.className = 'banner-ambiental sem-dados';
        banner.innerHTML = '<span>🌿 Camada ambiental: clique para carregar KMZ</span>';
        banner.onclick = solicitarKmzAmbiental;
        return;
    }

    const incidencias = [];
    for (let i = 0; i < AmbientalState.poligonos.length; i++) {
        const poly = AmbientalState.poligonos[i];
        if (poly.pontos && rayCastingPontoEmPoligono(lat, lon, poly.pontos)) {
            incidencias.push(poly.nome || poly.categoria || 'Restrição');
        }
    }

    if (incidencias.length > 0) {
        banner.className = 'banner-ambiental alerta';
        banner.innerHTML = `<span>⚠️ <b>INCIDÊNCIA AMBIENTAL:</b> ${incidencias.join(' | ')}</span>`;
        banner.onclick = null;
        AmbientalState.ultimaIncidencia = incidencias.join(', ');
    } else {
        banner.className = 'banner-ambiental livre';
        banner.innerHTML = '<span>🌿 <b>Livre</b> de Restrições Ambientais</span>';
        banner.onclick = null;
        AmbientalState.ultimaIncidencia = null;
    }
}

// Exporta para escopo global
window.AmbientalState = AmbientalState;
window.toggleCamadaAmbiental = toggleCamadaAmbiental;
window.solicitarKmzAmbiental = solicitarKmzAmbiental;
window.carregarPoligonosAmbientais = carregarPoligonosAmbientais;
window.auditarPontoAmbiental = auditarPontoAmbiental;
window.rayCastingPontoEmPoligono = rayCastingPontoEmPoligono;
