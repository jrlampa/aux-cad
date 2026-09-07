/* ==========================================================================
   AUX CAD - Lógica do Estúdio Web de Postes & Cargas (app.js)
   ========================================================================== */

let map = null;
let postes = [];
let currentPosteId = null;
let markersMap = {};
let polylinesLayer = null;

// Configuração das Camadas de Satélite (Zero Custo)
const layers = {
  esri: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    maxZoom: 19
  }),
  google: L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
    attribution: '&copy; Google Maps',
    maxZoom: 20
  }),
  osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  })
};

let currentLayer = layers.esri;

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  carregarPostesServidor();
});

function initMap() {
  // Padrão inicial: Região Sudeste / Rio de Janeiro
  map = L.map('map', {
    center: [-22.9068, -43.1729],
    zoom: 17,
    layers: [currentLayer]
  });

  polylinesLayer = L.layerGroup().addTo(map);

  // Evento de Clique no Mapa para adicionar Poste
  map.on('click', (e) => {
    adicionarNovoPoste(e.latlng.lat, e.latlng.lng);
  });
}

function trocarCamada(tipo) {
  map.removeLayer(currentLayer);
  currentLayer = layers[tipo];
  map.addLayer(currentLayer);

  document.querySelectorAll('.btn-layer').forEach(b => b.classList.remove('active'));
  document.getElementById(`btn${tipo.charAt(0).toUpperCase() + tipo.slice(1)}`).classList.add('active');
}

// Carrega os postes salvos no backend
async function carregarPostesServidor() {
  try {
    const res = await fetch('/api/postes');
    if (res.ok) {
      const dados = await res.json();
      postes = dados;
      renderizarTodosPostes();
      if (postes.length > 0) {
        centralizarNosPostes();
      }
    }
  } catch (err) {
    console.warn('Servidor offline ou sem postes prévios:', err);
  }
}

// Adiciona novo poste no ponto clicado
function adicionarNovoPoste(lat, lon) {
  const proximoNumero = sugerirProximoNumero();
  const novoId = 'p_' + Date.now();

  const novoPoste = {
    id: novoId,
    numero: proximoNumero,
    lat: lat,
    lon: lon,
    x_utm: 0,
    y_utm: 0,
    fuso: 23,
    tipo_poste: "11/M",
    estrutura_mt: "N1",
    estrutura_bt: "S1",
    equipamentos: [],
    clientes_mono: 0,
    clientes_bi: 0,
    clientes_tri: 0,
    cargas_especiais: [],
    observacao: ""
  };

  postes.push(novoPoste);
  renderizarTodosPostes();
  abrirDrawerParaPoste(novoId);
  salvarNoServidor();
  showToast(`Poste ${proximoNumero} inserido no mapa!`);
}

function sugerirProximoNumero() {
  let maiorNum = 0;
  postes.forEach(p => {
    const n = parseInt(p.numero, 10);
    if (!isNaN(n) && n > maiorNum) {
      maiorNum = n;
    }
  });
  return String(maiorNum + 1).padStart(2, '0');
}

// Renderiza marcadores e traçado
function renderizarTodosPostes() {
  // Limpa marcadores
  Object.values(markersMap).forEach(m => map.removeLayer(m));
  markersMap = {};
  polylinesLayer.clearLayers();

  const coordsRota = [];

  postes.forEach(p => {
    const marker = L.marker([p.lat, p.lon], {
      draggable: true,
      icon: L.divIcon({
        className: 'custom-pole-icon',
        html: `<span>${p.numero}</span>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      })
    });

    marker.on('click', () => {
      abrirDrawerParaPoste(p.id);
    });

    marker.on('dragend', (e) => {
      const pos = e.target.getLatLng();
      p.lat = pos.lat;
      p.lon = pos.lng;
      renderizarTodosPostes();
      salvarNoServidor();
    });

    marker.addTo(map);
    markersMap[p.id] = marker;
    coordsRota.push([p.lat, p.lon]);
  });

  // Linha conectando os postes (rede aérea)
  if (coordsRota.length > 1) {
    const polyline = L.polyline(coordsRota, {
      color: '#00E5FF',
      weight: 3.5,
      dashArray: '6, 6',
      opacity: 0.9
    });
    polylinesLayer.addLayer(polyline);
  }

  document.getElementById('badgePostes').textContent = `${postes.length} Postes no Traçado`;
}

function centralizarNosPostes() {
  if (postes.length === 0) return;
  const bounds = L.latLngBounds(postes.map(p => [p.lat, p.lon]));
  map.fitBounds(bounds, { padding: [50, 50], maxZoom: 18 });
}

// Drawer de Edição
function abrirDrawerParaPoste(id) {
  currentPosteId = id;
  const p = postes.find(item => item.id === id);
  if (!p) return;

  document.getElementById('drawerTitulo').textContent = `Poste ${p.numero}`;
  document.getElementById('txtNumero').value = p.numero;
  document.getElementById('lblLat').textContent = p.lat.toFixed(6);
  document.getElementById('lblLon').textContent = p.lon.toFixed(6);
  document.getElementById('lblUTM').textContent = p.x_utm ? `${p.x_utm} / ${p.y_utm}` : 'Automático';

  // Tipo de Poste
  document.getElementById('txtTipoPoste').value = p.tipo_poste;
  sincronizarChips('chipsTipoPoste', p.tipo_poste);

  // Estrutura MT
  document.getElementById('txtEstruturaMT').value = p.estrutura_mt;
  sincronizarChips('chipsMT', p.estrutura_mt);

  // Estrutura BT
  document.getElementById('txtEstruturaBT').value = p.estrutura_bt;
  sincronizarChips('chipsBT', p.estrutura_bt);

  // Equipamentos
  sincronizarMultiChips('chipsEquipamentos', p.equipamentos || []);

  // Clientes
  document.getElementById('cntMono').value = p.clientes_mono || 0;
  document.getElementById('cntBi').value = p.clientes_bi || 0;
  document.getElementById('cntTri').value = p.clientes_tri || 0;

  // Cargas Especiais com kVA e kW interligados (FP = 0.92)
  const lblStatus = document.getElementById('lblPotenciaStatus');
  if (p.cargas_especiais && p.cargas_especiais.length > 0) {
    const cEsp = p.cargas_especiais[0];
    document.getElementById('txtCargaDesc').value = cEsp.descricao || '';
    const kw = cEsp.potencia_kw || 0;
    const kva = cEsp.potencia_kva || (kw > 0 ? Number((kw / 0.92).toFixed(2)) : '');
    document.getElementById('txtCargaKva').value = kva || '';
    document.getElementById('txtCargaKw').value = kw || '';
    if (kva > 0 && kw > 0) {
      lblStatus.innerHTML = `✅ Carga configurada: <strong>${kva} kVA</strong> (${kw} kW com FP=0.92)`;
    } else {
      lblStatus.innerHTML = '💡 Digite kVA ou kW: a conversão é calculada automaticamente com FP = 0.92.';
    }
  } else {
    document.getElementById('txtCargaDesc').value = '';
    document.getElementById('txtCargaKva').value = '';
    document.getElementById('txtCargaKw').value = '';
    lblStatus.innerHTML = '💡 Digite kVA ou kW: a conversão é calculada automaticamente com FP = 0.92.';
  }

  // Obs
  document.getElementById('txtObs').value = p.observacao || '';

  document.getElementById('posteDrawer').classList.add('open');
}

function fecharDrawer() {
  document.getElementById('posteDrawer').classList.remove('open');
  currentPosteId = null;
}

// Funções de Carga Especial Trifásica & Conversão FP = 0.92
const FP_PADRAO = 0.92;

function setDescCarga(nome) {
  const input = document.getElementById('txtCargaDesc');
  input.value = nome;
  input.focus();
}

function converterPotencia(origem) {
  const inputKva = document.getElementById('txtCargaKva');
  const inputKw = document.getElementById('txtCargaKw');
  const lblStatus = document.getElementById('lblPotenciaStatus');

  if (origem === 'kva') {
    const valKva = parseFloat(inputKva.value);
    if (!isNaN(valKva) && valKva > 0) {
      const calcKw = Number((valKva * FP_PADRAO).toFixed(2));
      inputKw.value = calcKw;
      lblStatus.innerHTML = `⚡ <strong>${valKva.toFixed(1)} kVA</strong> convertidos para <strong>${calcKw.toFixed(2)} kW</strong> (FP = 0.92)`;
    } else {
      inputKw.value = '';
      lblStatus.innerHTML = '💡 Digite kVA ou kW: a conversão é calculada automaticamente com FP = 0.92.';
    }
  } else if (origem === 'kw') {
    const valKw = parseFloat(inputKw.value);
    if (!isNaN(valKw) && valKw > 0) {
      const calcKva = Number((valKw / FP_PADRAO).toFixed(2));
      inputKva.value = calcKva;
      lblStatus.innerHTML = `⚡ <strong>${valKw.toFixed(1)} kW</strong> convertidos para <strong>${calcKva.toFixed(2)} kVA</strong> (FP = 0.92)`;
    } else {
      inputKva.value = '';
      lblStatus.innerHTML = '💡 Digite kVA ou kW: a conversão é calculada automaticamente com FP = 0.92.';
    }
  }
}

function salvarPosteAtual() {
  if (!currentPosteId) return;
  const p = postes.find(item => item.id === currentPosteId);
  if (!p) return;

  p.numero = document.getElementById('txtNumero').value.trim() || p.numero;
  p.tipo_poste = document.getElementById('txtTipoPoste').value.trim();
  p.estrutura_mt = document.getElementById('txtEstruturaMT').value.trim();
  p.estrutura_bt = document.getElementById('txtEstruturaBT').value.trim();

  // Coleta Equipamentos ativos
  p.equipamentos = [];
  document.querySelectorAll('#chipsEquipamentos .chip-toggle.active').forEach(b => {
    p.equipamentos.push(b.textContent.trim());
  });

  // Clientes
  p.clientes_mono = parseInt(document.getElementById('cntMono').value, 10) || 0;
  p.clientes_bi = parseInt(document.getElementById('cntBi').value, 10) || 0;
  p.clientes_tri = parseInt(document.getElementById('cntTri').value, 10) || 0;

  // Carga Especial Trifásica com kVA e kW
  const descCarga = document.getElementById('txtCargaDesc').value.trim();
  let kvaCarga = parseFloat(document.getElementById('txtCargaKva').value) || 0;
  let kwCarga = parseFloat(document.getElementById('txtCargaKw').value) || 0;

  if (kvaCarga > 0 && kwCarga <= 0) {
    kwCarga = Number((kvaCarga * FP_PADRAO).toFixed(2));
  } else if (kwCarga > 0 && kvaCarga <= 0) {
    kvaCarga = Number((kwCarga / FP_PADRAO).toFixed(2));
  }

  p.cargas_especiais = [];
  if (descCarga || kvaCarga > 0 || kwCarga > 0) {
    p.cargas_especiais.push({
      descricao: descCarga || 'Carga Especial',
      potencia_kva: kvaCarga,
      potencia_kw: kwCarga,
      fp: FP_PADRAO,
      tipo: 'Trifásica'
    });
  }

  p.observacao = document.getElementById('txtObs').value.trim();

  renderizarTodosPostes();
  salvarNoServidor();
  fecharDrawer();
  showToast(`Poste ${p.numero} atualizado com sucesso!`);
}

function excluirPosteAtual() {
  if (!currentPosteId) return;
  postes = postes.filter(item => item.id !== currentPosteId);
  renderizarTodosPostes();
  salvarNoServidor();
  fecharDrawer();
  showToast('Poste removido do traçado.');
}

// Helpers de Chips e Contadores
function selecionarChip(btn, targetInputId) {
  const container = btn.parentElement;
  container.querySelectorAll('.chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(targetInputId).value = btn.textContent;
}

function sincronizarChips(containerId, valor) {
  document.querySelectorAll(`#${containerId} .chip`).forEach(b => {
    if (b.textContent === valor) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });
}

function toggleMultiChip(btn) {
  btn.classList.toggle('active');
}

function sincronizarMultiChips(containerId, listaValores) {
  document.querySelectorAll(`#${containerId} .chip-toggle`).forEach(b => {
    if (listaValores.includes(b.textContent.trim())) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });
}

function ajustarContador(id, delta) {
  const input = document.getElementById(id);
  let val = parseInt(input.value, 10) || 0;
  val = Math.max(0, val + delta);
  input.value = val;
}

// Sincronização e Ações com o Backend
async function salvarNoServidor() {
  try {
    await fetch('/api/postes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: jsonPostesString()
    });
  } catch (e) {
    console.error('Falha ao sincronizar com servidor:', e);
  }
}

function jsonPostesString() {
  return JSON.stringify({ postes: postes });
}

async function enviarParaAutoCAD() {
  if (postes.length === 0) {
    showToast('Adicione pelo menos 1 poste antes de enviar ao AutoCAD!');
    return;
  }
  await salvarNoServidor();

  try {
    const res = await fetch('/api/enviar-cad', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      showToast(`✔ ${data.msg}`);
      alert(`SUCESSO!\n\n${data.msg}\n\nPara carregar no AutoCAD aberto:\n1. Digite no AutoCAD: (load "${data.script_lsp.replace(/\\/g, '/')}")\nOu digite no AutoCAD o comando: MAPAPOSTES`);
    } else {
      showToast('Erro ao preparar arquivo para AutoCAD.');
    }
  } catch (err) {
    showToast('Falha na comunicação com o backend.');
  }
}

async function exportarKMZ() {
  if (postes.length === 0) {
    showToast('Nenhum poste cadastrado para exportar.');
    return;
  }
  await salvarNoServidor();

  try {
    const res = await fetch('/api/exportar-kmz', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      showToast('KMZ gerado com sucesso!');
      alert(`Arquivo KMZ pronto para o Google Earth em:\n${data.caminho_kmz}`);
    }
  } catch (err) {
    showToast('Falha ao exportar KMZ.');
  }
}

// Busca de Localização (Nominatim OSM)
async function buscarLocalizacao() {
  const query = document.getElementById('inputBusca').value.trim();
  if (!query) return;

  // Se for coordenadas no formato: lat, lon
  const partesCoord = query.split(',');
  if (partesCoord.length === 2) {
    const lat = parseFloat(partesCoord[0]);
    const lon = parseFloat(partesCoord[1]);
    if (!isNaN(lat) && !isNaN(lon)) {
      map.setView([lat, lon], 18);
      showToast('Posicionado nas coordenadas informadas!');
      return;
    }
  }

  showToast('Buscando localização...');
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`;
    const res = await fetch(url);
    const dados = await res.json();
    if (dados && dados.length > 0) {
      const lat = parseFloat(dados[0].lat);
      const lon = parseFloat(dados[0].lon);
      map.setView([lat, lon], 17);
      showToast(`Localizado: ${dados[0].display_name.split(',')[0]}`);
    } else {
      showToast('Local não encontrado. Tente cidade ou coordenadas.');
    }
  } catch (err) {
    showToast('Erro ao pesquisar endereço.');
  }
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3500);
}

// ==========================================================================
// Lançamento por Coordenadas do Croqui de Campo
// ==========================================================================

let abaCoordAtiva = 'utm';

function abrirModalCoordenadas() {
  document.getElementById('modalCoordenadas').classList.add('open');
  alternarAbaCoord('utm');
}

function fecharModalCoordenadas() {
  document.getElementById('modalCoordenadas').classList.remove('open');
}

function alternarAbaCoord(aba) {
  abaCoordAtiva = aba;
  if (aba === 'utm') {
    document.getElementById('tabUtm').classList.add('active');
    document.getElementById('tabLatLon').classList.remove('active');
    document.getElementById('painelUtm').style.display = 'block';
    document.getElementById('painelLatLon').style.display = 'none';
  } else {
    document.getElementById('tabLatLon').classList.add('active');
    document.getElementById('tabUtm').classList.remove('active');
    document.getElementById('painelLatLon').style.display = 'block';
    document.getElementById('painelUtm').style.display = 'none';
  }
}

async function confirmarLancamentoCoordenada() {
  let lat = 0, lon = 0, x_utm = 0, y_utm = 0, fuso = 23;

  if (abaCoordAtiva === 'utm') {
    x_utm = parseFloat(document.getElementById('inputUtmX').value);
    y_utm = parseFloat(document.getElementById('inputUtmY').value);
    fuso = parseInt(document.getElementById('inputUtmFuso').value, 10) || 23;

    if (isNaN(x_utm) || isNaN(y_utm)) {
      alert('Por favor, informe valores válidos para Easting X e Northing Y.');
      return;
    }

    try {
      const res = await fetch('/api/converter-coordenadas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tipo: 'utm', x: x_utm, y: y_utm, fuso: fuso })
      });
      const data = await res.json();
      if (data.ok) {
        lat = data.lat;
        lon = data.lon;
      }
    } catch (e) {
      alert('Falha ao converter coordenadas UTM.');
      return;
    }
  } else {
    lat = parseFloat(document.getElementById('inputLat').value);
    lon = parseFloat(document.getElementById('inputLon').value);

    if (isNaN(lat) || isNaN(lon)) {
      alert('Por favor, informe valores válidos para Latitude e Longitude.');
      return;
    }

    try {
      const res = await fetch('/api/converter-coordenadas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tipo: 'latlon', lat: lat, lon: lon, fuso: fuso })
      });
      const data = await res.json();
      if (data.ok) {
        x_utm = data.x_utm;
        y_utm = data.y_utm;
      }
    } catch (e) {
      console.warn('Conversão UTM offline');
    }
  }

  fecharModalCoordenadas();

  // Insere o poste na coordenada exata
  adicionarNovoPoste(lat, lon);

  // Atualiza com as coordenadas UTM calculadas
  const novoP = postes[postes.length - 1];
  if (novoP) {
    novoP.x_utm = x_utm;
    novoP.y_utm = y_utm;
    novoP.fuso = fuso;
    salvarNoServidor();
    abrirDrawerParaPoste(novoP.id);
  }

  // Voa no mapa com animação suave para o ponto
  map.flyTo([lat, lon], 19, { animate: true, duration: 1.2 });
  showToast(`Poste lançado em X: ${x_utm} / Y: ${y_utm}!`);
}

