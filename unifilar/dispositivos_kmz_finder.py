# -*- coding: utf-8 -*-
"""
dispositivos_kmz_finder.py - Localizador Geoespacial de Dispositivos MT em KMZ
Responsabilidade: Busca rápida e indexada de chaves fusíveis, religadores e chaves
nos arquivos KMZ de apoio com conversão geodésica analítica Snyder para coordenadas UTM.
"""

import os
import sys
import re
import math
import json
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

CAMINHO_PADRAO_KMZ = r"G:\Meu Drive\1-SATEL\KMZ\OneDrive_2026-04-16\MATERIAL DE APOIO\kmz - Dispositivos 05-2020 (1)\kmz - Dispositivos 05-2020"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "dispositivos_kmz_cache.json")


def latlon_to_utm(lat: float, lon: float, zone: int = 23, northern_hemisphere: bool = False) -> Tuple[float, float]:
    """Converte Latitude/Longitude (WGS84 / SIRGAS 2000) para UTM analítico Snyder."""
    a = 6378137.0
    f = 1 / 298.257223563
    e_sq = (2 * f) - (f ** 2)
    e_prime_sq = e_sq / (1 - e_sq)
    k0 = 0.9996

    lat_rad = math.radians(lat)
    lon_origin = (zone - 1) * 6 - 180 + 3
    lon_origin_rad = math.radians(lon_origin)
    lon_rad = math.radians(lon)

    delta_lon = lon_rad - lon_origin_rad

    sin_phi = math.sin(lat_rad)
    cos_phi = math.cos(lat_rad)
    tan_phi = math.tan(lat_rad)

    n = a / math.sqrt(1 - e_sq * (sin_phi ** 2))
    t = tan_phi ** 2
    c = e_prime_sq * (cos_phi ** 2)
    aa = cos_phi * delta_lon

    m = a * (
        (1 - e_sq / 4 - 3 * (e_sq ** 2) / 64 - 5 * (e_sq ** 3) / 256) * lat_rad
        - (3 * e_sq / 8 + 3 * (e_sq ** 2) / 32 + 45 * (e_sq ** 3) / 1024) * math.sin(2 * lat_rad)
        + (15 * (e_sq ** 2) / 256 + 45 * (e_sq ** 3) / 1024) * math.sin(4 * lat_rad)
        - (35 * (e_sq ** 3) / 3072) * math.sin(6 * lat_rad)
    )

    x = k0 * n * (
        aa + (1 - t + c) * (aa ** 3) / 6
        + (5 - 18 * t + (t ** 2) + 72 * c - 58 * e_prime_sq) * (aa ** 5) / 120
    ) + 500000.0

    y = k0 * (
        m + n * tan_phi * (
            (aa ** 2) / 2
            + (5 - t + 9 * c + 4 * (c ** 2)) * (aa ** 4) / 24
            + (61 - 58 * t + (t ** 2) + 600 * c - 330 * e_prime_sq) * (aa ** 6) / 720
        )
    )
    if not northern_hemisphere and y < 0:
        y += 10000000.0

    return x, y


def normalizar_chave_dispositivo(codigo: str) -> str:
    """Normaliza o código do dispositivo removendo caracteres não-alfanuméricos."""
    if not codigo:
        return ""
    # Remove espaços, hífens, pontos e caracteres especiais
    c = re.sub(r"[^A-Za-z0-9]", "", codigo.strip().upper())
    return c


def extrair_apenas_digitos(codigo: str) -> str:
    """Extrai apenas a parte numérica de um código."""
    if not codigo:
        return ""
    d = re.sub(r"\D", "", codigo)
    return d


def ler_dispositivos_de_kmz(caminho_kmz: str) -> Dict[str, Dict]:
    """Extrai todos os pontos de um arquivo KMZ com nome e coordenadas."""
    resultado = {}
    if not os.path.exists(caminho_kmz):
        return resultado

    try:
        with zipfile.ZipFile(caminho_kmz, "r") as z:
            for name in z.namelist():
                if name.lower().endswith(".kml"):
                    with z.open(name) as f:
                        root = ET.fromstring(f.read().decode("utf-8", errors="ignore"))
                        # Procura por Placemarks com Point
                        for p in root.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
                            pt = p.find("{http://www.opengis.net/kml/2.2}Point")
                            if pt is None:
                                continue
                            coords_elem = pt.find("{http://www.opengis.net/kml/2.2}coordinates")
                            if coords_elem is None or not coords_elem.text:
                                continue

                            nome_elem = p.find("{http://www.opengis.net/kml/2.2}name")
                            nome = nome_elem.text.strip() if nome_elem is not None and nome_elem.text else ""
                            if not nome:
                                continue

                            raw_coords = coords_elem.text.strip().split(",")
                            if len(raw_coords) >= 2:
                                try:
                                    lon = float(raw_coords[0])
                                    lat = float(raw_coords[1])
                                except ValueError:
                                    continue

                                chave_norm = normalizar_chave_dispositivo(nome)
                                info = {
                                    "nome_original": nome,
                                    "chave": chave_norm,
                                    "lat": lat,
                                    "lon": lon,
                                    "arquivo": os.path.basename(caminho_kmz)
                                }
                                resultado[chave_norm] = info
                                digitos = extrair_apenas_digitos(nome)
                                if digitos and len(digitos) >= 3:
                                    # Registra também pela chave puramente numérica
                                    resultado[f"NUM_{digitos}"] = info
    except Exception:
        pass

    return resultado


class DispositivosKmzIndex:
    """Índice inteligente de dispositivos com suporte a cache local rápido."""

    def __init__(self, pasta_kmz: Optional[str] = None, cache_file: Optional[str] = None):
        self.pasta_kmz = pasta_kmz or os.environ.get("PASTA_DISPOSITIVOS_KMZ", CAMINHO_PADRAO_KMZ)
        self.cache_file = cache_file or CACHE_FILE
        self.dados: Dict[str, Dict] = {}
        self._carregado = False

    def carregar_indice(self, forcar_reindex: bool = False):
        """Carrega dados do cache local ou escaneia os arquivos KMZ."""
        if self._carregado and not forcar_reindex:
            return

        # 1. Tenta carregar do cache JSON em disco
        if not forcar_reindex and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.dados = json.load(f)
                    if self.dados:
                        self._carregado = True
                        return
            except Exception:
                pass

        # 2. Se não houver cache ou for forçado, varre a pasta KMZ
        self.dados = {}
        if os.path.exists(self.pasta_kmz):
            arquivos = [
                os.path.join(self.pasta_kmz, f)
                for f in os.listdir(self.pasta_kmz)
                if f.lower().endswith(".kmz")
            ]
            for arq in arquivos:
                disps = ler_dispositivos_de_kmz(arq)
                self.dados.update(disps)

            # Salva o cache para buscas instantâneas futuras (apenas se encontrou dados)
            if self.dados:
                try:
                    with open(self.cache_file, "w", encoding="utf-8") as f:
                        json.dump(self.dados, f, ensure_ascii=False)
                except Exception:
                    pass

        self._carregado = True

    def buscar(self, codigo: str, fuso_utm: int = 23) -> Optional[Dict]:
        """Busca um dispositivo por código (ex: 'CF 636018', 'AR010625', '636018')."""
        self.carregar_indice()
        if not codigo:
            return None

        chave = normalizar_chave_dispositivo(codigo)

        # 1. Busca direta por chave normalizada
        disp = self.dados.get(chave)

        # 2. Se começar com 'CF' ou 'RL', tenta sem o prefixo
        if not disp and (chave.startswith("CF") or chave.startswith("RL") or chave.startswith("AR")):
            disp = self.dados.get(chave[2:])

        # 3. Tenta prefixando 'CF' se o usuário passou só números
        if not disp and chave.isdigit():
            disp = self.dados.get(f"CF{chave}")
            if not disp:
                disp = self.dados.get(f"NUM_{chave}")

        # 4. Tenta busca por correspondência de dígitos
        if not disp:
            digitos = extrair_apenas_digitos(codigo)
            if digitos and len(digitos) >= 4:
                disp = self.dados.get(f"NUM_{digitos}")

        if disp:
            x, y = latlon_to_utm(disp["lat"], disp["lon"], zone=fuso_utm)
            tipo_disp = "REL" if "RL" in disp["nome_original"].upper() or "REL" in disp["nome_original"].upper() else "CHAVE"
            return {
                "encontrado": True,
                "codigo_buscado": codigo,
                "nome_original": disp["nome_original"],
                "tipo": tipo_disp,
                "lat": disp["lat"],
                "lon": disp["lon"],
                "utm_x": round(x, 2),
                "utm_y": round(y, 2),
                "fuso": fuso_utm,
                "arquivo": disp["arquivo"]
            }

        return None


# Instância global reutilizável
_INDEX_GLOBAL = DispositivosKmzIndex()


def buscar_dispositivo_kmz(codigo: str, fuso_utm: int = 23, pasta_kmz: Optional[str] = None) -> Optional[Dict]:
    """Interface funcional rápida para busca de dispositivo nos KMZs."""
    if pasta_kmz:
        idx = DispositivosKmzIndex(pasta_kmz)
        return idx.buscar(codigo, fuso_utm)
    return _INDEX_GLOBAL.buscar(codigo, fuso_utm)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Localizador de Dispositivos MT em KMZ")
    parser.add_argument("--codigo", required=True, help="Código do dispositivo (ex: CF 636018, AR010625)")
    parser.add_argument("--fuso", type=int, default=23, help="Fuso UTM (padrão 23)")
    parser.add_argument("--kmz-dir", default=None, help="Pasta contendo os arquivos KMZ")
    parser.add_argument("--json", action="store_true", help="Imprimir saída em formato JSON")

    args = parser.parse_args()
    res = buscar_dispositivo_kmz(args.codigo, args.fuso, args.kmz_dir)

    if args.json:
        print(json.dumps(res or {"encontrado": False, "codigo": args.codigo}, ensure_ascii=False, indent=2))
    else:
        if res:
            print(f"[OK] Dispositivo encontrado: {res['nome_original']}")
            print(f"  Tipo: {res['tipo']} | Arquivo: {res['arquivo']}")
            print(f"  Coordenadas GPS: {res['lat']:.6f}, {res['lon']:.6f}")
            print(f"  Coordenadas UTM: X={res['utm_x']:.2f}, Y={res['utm_y']:.2f} (Fuso {res['fuso']}S)")
        else:
            print(f"[AVISO] Dispositivo '{args.codigo}' não encontrado nos KMZs de apoio.")
