"""
Servidor Backend do Painel Web de Satélite Integrado (mapa_postes/mapa_servidor.py).
Fornece API REST local para o mapa interativo de satélite, persistência de postes,
conversão geodésica analítica Snyder, geração de scripts LISP para o AutoCAD e exportação de KMZ.
"""

import argparse
import html
import http.server
import json
import math
import os
import socketserver
import sys
import threading
import webbrowser
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

# Importa conversor geodésico compartilhado da topografia
from topografia.kmz_pontos_importer import latlon_to_utm, detectar_fuso_utm


def utm_to_latlon(easting: float, northing: float, zone: int, northern_hemisphere: bool = False) -> Tuple[float, float]:
    """Converte coordenadas UTM (SIRGAS 2000 / WGS84) para Latitude / Longitude (graus decimais)."""
    a = 6378137.0
    f = 1 / 298.257223563
    b = a * (1 - f)
    e_sq = (a**2 - b**2) / (a**2)
    e_prime_sq = (a**2 - b**2) / (b**2)
    k0 = 0.9996

    x = easting - 500000.0
    y = northing
    if not northern_hemisphere:
        y -= 10000000.0

    long_origin = (zone - 1) * 6 - 180 + 3
    m = y / k0
    mu = m / (a * (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256))
    e1 = (1 - math.sqrt(1 - e_sq)) / (1 + math.sqrt(1 - e_sq))

    phi1_rad = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    n1 = a / math.sqrt(1 - e_sq * math.sin(phi1_rad) ** 2)
    t1 = math.tan(phi1_rad) ** 2
    c1 = e_prime_sq * math.cos(phi1_rad) ** 2
    r1 = a * (1 - e_sq) / ((1 - e_sq * math.sin(phi1_rad) ** 2) ** 1.5)
    d = x / (n1 * k0)

    lat_rad = phi1_rad - (n1 * math.tan(phi1_rad) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e_prime_sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e_prime_sq - 3 * c1**2) * d**6 / 720
    )
    lat = math.degrees(lat_rad)

    lon_rad = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e_prime_sq + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1_rad)
    lon = long_origin + math.degrees(lon_rad)

    return lat, lon



def converter_potencia_trifasica(kw: float = 0.0, kva: float = 0.0, fp: float = 0.92) -> tuple[float, float]:
    """Converte entre kW e kVA usando Fator de Potência padrão de 0.92."""
    if kva > 0 and kw <= 0:
        kw = round(kva * fp, 2)
    elif kw > 0 and kva <= 0:
        kva = round(kw / fp, 2)
    return kw, kva


@dataclass
class CargaEspecial:
    descricao: str = ""
    potencia_kw: float = 0.0
    potencia_kva: float = 0.0
    fp: float = 0.92
    tipo: str = "Trifásica"


@dataclass
class PosteStudio:
    id: str
    numero: str
    lat: float
    lon: float
    x_utm: float
    y_utm: float
    fuso: int = 23
    tipo_poste: str = "11/M"
    estrutura_mt: str = "N1"
    estrutura_bt: str = "S1"
    estruturas_mt: List[str] = field(default_factory=list)
    estruturas_bt: List[str] = field(default_factory=list)
    tem_trafo: bool = False
    potencia_trafo: str = "45kVA"
    equipamentos: List[str] = field(default_factory=list)
    clientes_mono: int = 0
    clientes_bi: int = 0
    clientes_tri: int = 0
    cargas_especiais: List[Dict] = field(default_factory=list)
    observacao: str = ""


class EstadoProjeto:
    def __init__(self, caminho_persist: str):
        self.caminho_persist = caminho_persist
        self.postes: Dict[str, PosteStudio] = {}
        self.fuso_padrao = 23
        self.carregar()

    def carregar(self):
        if os.path.exists(self.caminho_persist):
            try:
                with open(self.caminho_persist, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    self.fuso_padrao = dados.get("fuso_padrao", 23)
                    for item in dados.get("postes", []):
                        p = PosteStudio(**item)
                        self.postes[p.id] = p
            except Exception as e:
                print(f"[AVISO] Falha ao carregar estado: {e}", file=sys.stderr)

    def salvar(self):
        dados = {
            "fuso_padrao": self.fuso_padrao,
            "postes": [asdict(p) for p in self.postes.values()]
        }
        os.makedirs(os.path.dirname(os.path.abspath(self.caminho_persist)), exist_ok=True)
        with open(self.caminho_persist, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)


def gerar_lisp_postes_studio(
    postes: List[PosteStudio],
    caminho_saida_lsp: str,
    offset_num_x: float = -3.0,
    offset_num_y: float = -3.0,
    offset_txt_x: float = 3.0,
    offset_txt_y: float = 0.8
) -> str:
    """Gera rotina AutoLISP enriquecida com postes, estruturas e anotações de clientes/cargas."""
    linhas = [
        ";;; =============================================================================",
        ";;; Script Gerado pelo Painel Web de Satélite (mapa_postes)",
        ";;; Insere bloco 'POSTE_', bloco 'PONTO' e descrições técnicas de cargas/estruturas.",
        ";;; =============================================================================",
        "(vl-load-com)",
        "",
        "(defun c:EXEC_IMPORT_STUDIO ( / acad doc space layers layObj c p blkName pBase pNum pTxt mTextObj atts tag )",
        "  (setq acad (vlax-get-acad-object))",
        "  (setq doc (vla-get-ActiveDocument acad))",
        "  (if (= (getvar \"CVPORT\") 1)",
        "    (setq space (vla-get-PaperSpace doc))",
        "    (setq space (vla-get-ModelSpace doc))",
        "  )",
        "  (setq layers (vla-get-Layers doc))",
        "",
        "  (defun criar-camada (nome cor / l)",
        "    (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-Item (list layers nome)))",
        "      (progn (setq l (vla-Add layers nome)) (vla-put-Color l cor))",
        "    )",
        "  )",
        "",
        "  (criar-camada \"POSTES_SIMBOLO\" 3)    ; Verde",
        "  (criar-camada \"POSTES_NUMERO\" 3)     ; Verde",
        "  (criar-camada \"POSTES_DESCRICAO\" 7)  ; Branco",
        "  (criar-camada \"POSTES_CARGAS\" 1)     ; Vermelho",
        "",
        "  (vla-StartUndoMark doc)",
        ""
    ]

    for p in postes:
        x = p.x_utm
        y = p.y_utm
        num_x = round(x + offset_num_x, 3)
        num_y = round(y + offset_num_y, 3)
        txt_x = round(num_x + offset_txt_x, 3)
        txt_y = round(num_y + offset_txt_y, 3)

        num_esc = p.numero.replace('"', '\\"')

        # Linhas descritivas do poste
        desc_linhas = [p.tipo_poste]
        if p.estruturas_mt:
            for mt in p.estruturas_mt:
                if mt and mt != "Nenhum":
                    desc_linhas.append(mt)
        elif p.estrutura_mt and p.estrutura_mt != "Nenhum":
            desc_linhas.append(p.estrutura_mt)

        if p.estruturas_bt:
            for bt in p.estruturas_bt:
                if bt and bt != "Nenhum":
                    desc_linhas.append(bt)
        elif p.estrutura_bt and p.estrutura_bt != "Nenhum":
            desc_linhas.append(p.estrutura_bt)

        tem_trafo = p.tem_trafo or any("TRAFO" in eq.upper() for eq in p.equipamentos)

        for eq in p.equipamentos:
            if eq:
                desc_linhas.append(eq)

        # Resumo de clientes e cargas especiais
        cargas_resumo = []
        if p.clientes_mono > 0:
            cargas_resumo.append(f"{p.clientes_mono}M")
        if p.clientes_bi > 0:
            cargas_resumo.append(f"{p.clientes_bi}B")
        if p.clientes_tri > 0:
            cargas_resumo.append(f"{p.clientes_tri}T")

        cargas_especiais_linhas = []
        for ce in p.cargas_especiais:
            desc = ce.get("descricao", "").strip() or "Carga"
            kw = float(ce.get("potencia_kw") or 0.0)
            kva = float(ce.get("potencia_kva") or 0.0)
            fp = float(ce.get("fp") or 0.92)
            kw, kva = converter_potencia_trifasica(kw, kva, fp)

            if kva > 0 and kw > 0:
                cargas_especiais_linhas.append(f"{desc.upper()} {kva:g}kVA ({kw:g}kW)")
                cargas_resumo.append(f"{desc[:4].upper()} {kva:g}kVA")
            elif kva > 0:
                cargas_especiais_linhas.append(f"{desc.upper()} {kva:g}kVA")
                cargas_resumo.append(f"{desc[:4].upper()} {kva:g}kVA")
            elif kw > 0:
                cargas_especiais_linhas.append(f"{desc.upper()} {kw:g}kW")
                cargas_resumo.append(f"{desc[:4].upper()} {kw:g}kW")

        if cargas_resumo:
            desc_linhas.append("CLI: " + "/".join(cargas_resumo))
        for ce_linha in cargas_especiais_linhas:
            desc_linhas.append(f"CARGA TRI: {ce_linha}")

        if p.observacao:
            desc_linhas.append(p.observacao)

        linhas.extend([
            f"  ;; --- Poste {num_esc} ---",
            f"  (setq pBase (vlax-3d-point (list {x} {y} 0.0)))",
            f"  (setq pNum  (vlax-3d-point (list {num_x} {num_y} 0.0)))",
            "",
            "  ;; A) Bloco 'POSTE_'",
            "  (if (tblsearch \"BLOCK\" \"POSTE_\")",
            f"    (progn (setq blk (vla-InsertBlock space pBase \"POSTE_\" 1.0 1.0 1.0 0.0)) (vla-put-Layer blk \"POSTES_SIMBOLO\"))",
            f"    (progn (setq c (vla-AddCircle space pBase 0.6)) (vla-put-Layer c \"POSTES_SIMBOLO\") (setq ptObj (vla-AddPoint space pBase)) (vla-put-Layer ptObj \"POSTES_SIMBOLO\"))",
            "  )",
            ""
        ])

        if tem_trafo:
            linhas.extend([
                "  ;; Inserção do Bloco de Transformador ('TRAFO1', 'TRAFO' ou 'T')",
                "  (setq blk-trafo (cond ((tblsearch \"BLOCK\" \"TRAFO1\") \"TRAFO1\") ((tblsearch \"BLOCK\" \"TRAFO\") \"TRAFO\") ((tblsearch \"BLOCK\" \"T\") \"T\") (t nil)))",
                "  (if blk-trafo",
                f"    (progn (setq blk (vla-InsertBlock space pBase blk-trafo 1.0 1.0 1.0 0.0)) (vla-put-Layer blk \"POSTES_SIMBOLO\"))",
                f"    (progn (setq c1 (vla-AddCircle space (vlax-3d-point (list {x} {round(y + 0.35, 3)} 0.0)) 0.35)) (vla-put-Layer c1 \"POSTES_SIMBOLO\") (setq c2 (vla-AddCircle space (vlax-3d-point (list {x} {round(y + 1.05, 3)} 0.0)) 0.35)) (vla-put-Layer c2 \"POSTES_SIMBOLO\"))",
                "  )",
                ""
            ])

        linhas.extend([
            "",
            "  ;; B) Bloco 'PONTO'",
            "  (if (tblsearch \"BLOCK\" \"PONTO\")",
            "    (progn",
            f"      (setq blk (vla-InsertBlock space pNum \"PONTO\" 1.0 1.0 1.0 0.0))",
            "      (vla-put-Layer blk \"POSTES_NUMERO\")",
            "      (if (= (vla-get-HasAttributes blk) :vlax-true)",
            "        (foreach att (vlax-safearray->list (vlax-variant-value (vla-GetAttributes blk)))",
            f"          (vla-put-TextString att \"{num_esc}\")",
            "        )",
            "      )",
            "    )",
            "    (progn",
            f"      (setq c (vla-AddCircle space pNum 1.8))",
            "      (vla-put-Layer c \"POSTES_NUMERO\")",
            f"      (setq tObj (vla-AddText space \"{num_esc}\" pNum 1.8))",
            "      (vla-put-Alignment tObj 10)",
            "      (vla-put-TextAlignmentPoint tObj pNum)",
            "      (vla-put-Layer tObj \"POSTES_NUMERO\")",
            "    )",
            "  )",
            ""
        ])

        altura_texto = 1.8
        espacamento_y = 2.60
        for idx_l, texto in enumerate(desc_linhas):
            cur_y = round(txt_y - (idx_l * espacamento_y), 3)
            texto_esc = texto.replace('"', '\\"')
            layer_texto = "POSTES_CARGAS" if "CLI:" in texto else "POSTES_DESCRICAO"
            linhas.extend([
                f"  (setq tObj (vla-AddText space \"{texto_esc}\" (vlax-3d-point (list {txt_x} {cur_y} 0.0)) {altura_texto}))",
                f"  (vla-put-Layer tObj \"{layer_texto}\")"
            ])
        linhas.append("")

    linhas.extend([
        "  (vla-EndUndoMark doc)",
        "  (vla-ZoomExtents acad)",
        f"  (princ \"\\n[Sucesso] {len(postes)} postes do Painel Web desenhados no AutoCAD!\")",
        "  (princ)",
        ")",
        "(c:EXEC_IMPORT_STUDIO)",
        "(princ)"
    ])

    os.makedirs(os.path.dirname(os.path.abspath(caminho_saida_lsp)), exist_ok=True)
    with open(caminho_saida_lsp, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    return caminho_saida_lsp


def exportar_kmz_studio(postes: List[PosteStudio], caminho_kmz: str):
    """Gera arquivo KMZ compactado compatível com o Google Earth."""
    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        '    <name>Postes_Rede_Eletrica</name>'
    ]

    for p in postes:
        desc_linhas = [p.tipo_poste]
        if p.estrutura_mt and p.estrutura_mt != "Nenhum":
            desc_linhas.append(p.estrutura_mt)
        if p.estrutura_bt and p.estrutura_bt != "Nenhum":
            desc_linhas.append(p.estrutura_bt)
        for eq in p.equipamentos:
            desc_linhas.append(eq)

        cargas = []
        if p.clientes_mono > 0:
            cargas.append(f"{p.clientes_mono} Mono")
        if p.clientes_bi > 0:
            cargas.append(f"{p.clientes_bi} Bi")
        if p.clientes_tri > 0:
            cargas.append(f"{p.clientes_tri} Tri")
        for ce in p.cargas_especiais:
            cargas.append(f"{ce.get('descricao', 'Carga')} ({ce.get('potencia_kw', 0)}kW)")

        if cargas:
            desc_linhas.append("Clientes: " + ", ".join(cargas))
        if p.observacao:
            desc_linhas.append(p.observacao)

        desc_html = "<br/>".join(html.escape(l) for l in desc_linhas)

        kml_parts.extend([
            '    <Placemark>',
            f'      <name>{html.escape(p.numero)}</name>',
            f'      <description>{desc_html}</description>',
            '      <Point>',
            f'        <coordinates>{p.lon:.7f},{p.lat:.7f},0</coordinates>',
            '      </Point>',
            '    </Placemark>'
        ])

    kml_parts.extend([
        '  </Document>',
        '</kml>'
    ])

    kml_conteudo = "\n".join(kml_parts)
    os.makedirs(os.path.dirname(os.path.abspath(caminho_kmz)), exist_ok=True)
    with zipfile.ZipFile(caminho_kmz, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml_conteudo.encode("utf-8"))


class MapaHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, estado_projeto: EstadoProjeto = None, web_dir: str = "", **kwargs):
        self.estado = estado_projeto
        self.web_dir = web_dir
        super().__init__(*args, directory=web_dir, **kwargs)

    def do_GET(self):
        if self.path == "/api/postes":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            dados = [asdict(p) for p in self.estado.postes.values()]
            self.wfile.write(json.dumps(dados, ensure_ascii=False).encode("utf-8"))
            return
        return super().do_GET()

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode("utf-8") if tamanho > 0 else "{}"
        try:
            dados = json.loads(corpo)
        except json.JSONDecodeError:
            dados = {}

        if self.path == "/api/postes":
            # Atualiza lista completa de postes
            self.estado.postes.clear()
            for item in dados.get("postes", []):
                # Recalcula UTM por segurança
                lat = float(item["lat"])
                lon = float(item["lon"])
                fuso = int(item.get("fuso", self.estado.fuso_padrao))
                x_utm, y_utm = latlon_to_utm(lat, lon, fuso)
                item["x_utm"] = round(x_utm, 3)
                item["y_utm"] = round(y_utm, 3)
                p = PosteStudio(**item)
                self.estado.postes[p.id] = p
            self.estado.salvar()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "total": len(self.estado.postes)}).encode("utf-8"))
            return

        elif self.path == "/api/enviar-cad":
            # Gera rotina LISP na pasta do projeto e avisa o AutoCAD
            postes_lista = list(self.estado.postes.values())
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            saida_lsp = os.path.join(root_dir, "mapa_postes", "mapa_postes_exec.lsp")
            gerar_lisp_postes_studio(postes_lista, saida_lsp)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "total": len(postes_lista),
                "script_lsp": saida_lsp,
                "msg": f"{len(postes_lista)} postes preparados para inserção no AutoCAD!"
            }).encode("utf-8"))
            return

        elif self.path == "/api/exportar-kmz":
            postes_lista = list(self.estado.postes.values())
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            saida_kmz = os.path.join(root_dir, "mapa_postes", "postes_rede_campo.kmz")
            exportar_kmz_studio(postes_lista, saida_kmz)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "caminho_kmz": saida_kmz,
                "msg": f"Arquivo KMZ exportado com sucesso: {saida_kmz}"
            }).encode("utf-8"))
            return

        elif self.path == "/api/converter-coordenadas":
            tipo = dados.get("tipo", "utm")
            fuso = int(dados.get("fuso", self.estado.fuso_padrao))

            if tipo == "utm":
                x = float(dados.get("x", 0.0))
                y = float(dados.get("y", 0.0))
                lat, lon = utm_to_latlon(x, y, fuso)
            else:
                lat = float(dados.get("lat", 0.0))
                lon = float(dados.get("lon", 0.0))
                x, y = latlon_to_utm(lat, lon, fuso)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "x_utm": round(x, 3),
                "y_utm": round(y, 3),
                "fuso": fuso
            }).encode("utf-8"))
            return

        elif self.path == "/api/converter-potencia":
            kw = float(dados.get("kw") or 0.0)
            kva = float(dados.get("kva") or 0.0)
            fp = float(dados.get("fp") or 0.92)
            calc_kw, calc_kva = converter_potencia_trifasica(kw, kva, fp)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "kw": calc_kw,
                "kva": calc_kva,
                "fp": fp
            }).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()



def criar_servidor(porta: int = 8765, estado: EstadoProjeto = None, web_dir: str = ""):
    handler = lambda *args, **kwargs: MapaHandler(*args, estado_projeto=estado, web_dir=web_dir, **kwargs)
    server = socketserver.TCPServer(("127.0.0.1", porta), handler)
    return server


def iniciar_servidor_background(porta: int = 8765, persist_file: str = "", web_dir: str = ""):
    if not persist_file:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        persist_file = os.path.join(base_dir, "mapa_dados.json")
    if not web_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        web_dir = os.path.join(base_dir, "web")

    estado = EstadoProjeto(persist_file)
    try:
        server = criar_servidor(porta, estado, web_dir)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"[MAPA STUDIO] Servidor ativo em: http://localhost:{porta}")
        return server
    except OSError as e:
        print(f"[MAPA STUDIO] Servidor já ativo ou porta ocupada ({e}).")
        return None


def main():
    parser = argparse.ArgumentParser(description="Servidor Web de Satélite para Lançamento de Postes no AutoCAD")
    parser.add_argument("--porta", type=int, default=8765, help="Porta HTTP (padrão: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Não abre o navegador automaticamente")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(base_dir, "web")
    persist_file = os.path.join(base_dir, "mapa_dados.json")

    estado = EstadoProjeto(persist_file)
    server = criar_servidor(args.porta, estado, web_dir)

    url = f"http://localhost:{args.porta}"
    print(f"\n=======================================================")
    print(f"   MAPA STUDIO - LANÇAMENTO DE POSTES & CARGAS         ")
    print(f"   Acesse no navegador: {url}                          ")
    print(f"=======================================================\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[MAPA STUDIO] Servidor encerrado.")
        server.server_close()


if __name__ == "__main__":
    main()
