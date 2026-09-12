/**
 * snap_magnetico.js - Módulo de Snap Magnético aos Postes e Nós da Rede
 * Atrai suavemente o cursor e o traçado para postes existentes (DWG, Traçado, Régua)
 * dentro de um raio de atração configurável em pixels de tela.
 */

const SnapMagnetico = {
    ativo: true,
    raioPixels: 18,
    snapMarker: null,
    ultimoSnap: null,

    /**
     * Alterna o estado do Snap Magnético
     */
    toggle(forcar = null, mapa = null) {
        this.ativo = (forcar !== null) ? forcar : !this.ativo;
        const btn = document.getElementById('btnToggleSnap');
        if (btn) {
            if (this.ativo) {
                btn.classList.add('active');
                btn.innerHTML = '🧲 Snap: ON';
                btn.title = 'Snap Magnético ATIVO: Atrai o cursor para postes e vértices (18px)';
            } else {
                btn.classList.remove('active');
                btn.innerHTML = '🧲 Snap: OFF';
                btn.title = 'Snap Magnético DESATIVADO';
                this.limparIndicador(mapa);
            }
        }
        if (typeof showToast === 'function') {
            showToast(`Snap Magnético: ${this.ativo ? 'ATIVADO' : 'DESATIVADO'}`, 'info');
        }
    },

    /**
     * Busca o candidato mais próximo dentro do raio em pixels
     */
    buscarPontoSnap(latlng, mapa) {
        if (!this.ativo || !mapa || !latlng) {
            return { snapped: false, lat: latlng ? latlng.lat : 0, lon: latlng ? latlng.lng : 0 };
        }

        const pCursor = mapa.latLngToContainerPoint(latlng);
        let melhorCandidato = null;
        let menorDistanciaPx = this.raioPixels;

        // 1. Postes do traçado contínuo ativo
        if (window.TracadoState && window.TracadoState.pontos) {
            for (const p of window.TracadoState.pontos) {
                if (!p.lat || !p.lon) continue;
                const pTela = mapa.latLngToContainerPoint([p.lat, p.lon]);
                const dist = Math.hypot(pCursor.x - pTela.x, pCursor.y - pTela.y);
                if (dist < menorDistanciaPx) {
                    menorDistanciaPx = dist;
                    melhorCandidato = {
                        lat: p.lat,
                        lon: p.lon,
                        x: p.x,
                        y: p.y,
                        nome: p.numero ? `P${p.numero}` : 'Vértice Traçado',
                        origem: 'tracado'
                    };
                }
            }
        }

        // 2. Pontos da ferramenta de medição ativa
        if (window.MedicaoState && window.MedicaoState.pontos) {
            for (const p of window.MedicaoState.pontos) {
                if (!p.lat || !p.lon) continue;
                const pTela = mapa.latLngToContainerPoint([p.lat, p.lon]);
                const dist = Math.hypot(pCursor.x - pTela.x, pCursor.y - pTela.y);
                if (dist < menorDistanciaPx) {
                    menorDistanciaPx = dist;
                    melhorCandidato = {
                        lat: p.lat,
                        lon: p.lon,
                        x: p.x,
                        y: p.y,
                        nome: 'Ponto Medição',
                        origem: 'medicao'
                    };
                }
            }
        }

        // 3. Postes importados do DWG
        if (window.AppState && window.AppState.dwgMarkersLayer) {
            window.AppState.dwgMarkersLayer.eachLayer(layer => {
                if (typeof layer.getLatLng === 'function') {
                    const lPos = layer.getLatLng();
                    const pTela = mapa.latLngToContainerPoint(lPos);
                    const dist = Math.hypot(pCursor.x - pTela.x, pCursor.y - pTela.y);
                    if (dist < menorDistanciaPx) {
                        menorDistanciaPx = dist;
                        const tooltipText = layer.getTooltip() ? layer.getTooltip().getContent() : 'Poste DWG';
                        melhorCandidato = {
                            lat: lPos.lat,
                            lon: lPos.lng,
                            x: layer._utmX || 0,
                            y: layer._utmY || 0,
                            nome: tooltipText,
                            origem: 'dwg'
                        };
                    }
                }
            });
        }

        // 4. Marcador principal do poste se posicionado
        if (window.AppState && window.AppState.marker && window.AppState.currentLat) {
            const pTela = mapa.latLngToContainerPoint([window.AppState.currentLat, window.AppState.currentLon]);
            const dist = Math.hypot(pCursor.x - pTela.x, pCursor.y - pTela.y);
            if (dist < menorDistanciaPx) {
                menorDistanciaPx = dist;
                melhorCandidato = {
                    lat: window.AppState.currentLat,
                    lon: window.AppState.currentLon,
                    x: window.AppState.currentX || 0,
                    y: window.AppState.currentY || 0,
                    nome: 'Marcador Atual',
                    origem: 'marcador'
                };
            }
        }

        if (melhorCandidato) {
            this.ultimoSnap = melhorCandidato;
            this.atualizarIndicador(melhorCandidato, mapa);
            return {
                snapped: true,
                lat: melhorCandidato.lat,
                lon: melhorCandidato.lon,
                x: melhorCandidato.x,
                y: melhorCandidato.y,
                nome: melhorCandidato.nome,
                origem: melhorCandidato.origem
            };
        } else {
            this.limparIndicador(mapa);
            this.ultimoSnap = null;
            return {
                snapped: false,
                lat: latlng.lat,
                lon: latlng.lng
            };
        }
    },

    /**
     * Renderiza ou atualiza o anel visual pulsante de Snap
     */
    atualizarIndicador(cand, mapa) {
        if (!mapa) return;

        if (!this.snapMarker) {
            this.snapMarker = L.circleMarker([cand.lat, cand.lon], {
                radius: 9,
                color: '#06b6d4',       // Ciano magnético
                fillColor: '#22d3ee',
                fillOpacity: 0.45,
                weight: 2.5,
                className: 'snap-magnetico-marker'
            }).addTo(mapa);
        } else {
            this.snapMarker.setLatLng([cand.lat, cand.lon]);
            if (!mapa.hasLayer(this.snapMarker)) {
                this.snapMarker.addTo(mapa);
            }
        }

        // Tooltip compacto no anel de snap
        if (this.snapMarker.getTooltip()) {
            this.snapMarker.setTooltipContent(`🧲 ${cand.nome}`);
        } else {
            this.snapMarker.bindTooltip(`🧲 ${cand.nome}`, {
                permanent: false,
                direction: 'top',
                offset: [0, -8],
                className: 'snap-tooltip'
            });
        }
    },

    /**
     * Remove o indicador de snap
     */
    limparIndicador(mapa) {
        if (this.snapMarker && mapa && mapa.hasLayer(this.snapMarker)) {
            mapa.removeLayer(this.snapMarker);
        }
    }
};

// Exporta para escopo global
window.SnapMagnetico = SnapMagnetico;
