"""Planta do restaurante: paredes, mesas e bancadas.

Junta as posicoes do garcom_navigation/config/pontos.yaml com as medidas do
garcom_simulation/config/restaurante.yaml e devolve os moveis como formas
simples (caixas e cilindros). E usado por:
  - gerar_mundo.py: escreve o mundo do Gazebo e o mapa da navegacao;
  - simulador_2d.py: simula o laser batendo nos moveis.
"""
import math
import os

import yaml

PACOTE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
REPO = os.path.dirname(PACOTE)
PONTOS_PADRAO = os.path.join(REPO, "garcom_navigation", "config", "pontos.yaml")
MEDIDAS_PADRAO = os.path.join(PACOTE, "config", "restaurante.yaml")

# cores (vermelho, verde, azul de 0 a 1), as mesmas das telas
COR_PAREDE = (0.84, 0.93, 0.89)
COR_TAMPO = (0.99, 0.94, 0.81)
COR_PE = (0.06, 0.18, 0.18)
COR_CADEIRA = (0.45, 0.30, 0.18)
COR_BANCADA = {"estacao_cafe": (0.36, 0.55, 0.62), "estacao_croissant": (0.95, 0.69, 0.12)}


class Caixa:
    """Caixa de comprimento sx, largura sy e altura sz, centrada em (x, y)."""

    def __init__(self, nome, x, y, sx, sy, sz, yaw=0.0, cor=(0.7, 0.7, 0.7), tipo="parede"):
        self.nome, self.x, self.y = nome, x, y
        self.sx, self.sy, self.sz, self.yaw = sx, sy, sz, yaw
        self.cor, self.tipo = cor, tipo
        self._c, self._s = math.cos(yaw), math.sin(yaw)

    def _local(self, px, py):
        dx, dy = px - self.x, py - self.y
        return self._c * dx + self._s * dy, -self._s * dx + self._c * dy

    def contem(self, px, py, folga=0.0):
        lx, ly = self._local(px, py)
        return abs(lx) <= self.sx / 2 + folga and abs(ly) <= self.sy / 2 + folga

    def raio(self, ox, oy, dx, dy):
        """Distancia ate a caixa ao longo do raio (ox, oy) + t*(dx, dy), ou None."""
        lx, ly = self._local(ox, oy)
        ldx = self._c * dx + self._s * dy
        ldy = -self._s * dx + self._c * dy
        t_min, t_max = -math.inf, math.inf
        for o, d, meia in ((lx, ldx, self.sx / 2), (ly, ldy, self.sy / 2)):
            if abs(d) < 1e-12:
                if abs(o) > meia:
                    return None
                continue
            t1, t2 = (-meia - o) / d, (meia - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            t_min, t_max = max(t_min, t1), min(t_max, t2)
            if t_min > t_max:
                return None
        if t_max < 0:
            return None
        return max(t_min, 0.0)


class Cilindro:
    """Cilindro (ou disco, no chao) de raio r centrado em (x, y)."""

    def __init__(self, nome, x, y, r, altura, cor=(0.7, 0.7, 0.7), tipo="mesa"):
        self.nome, self.x, self.y, self.r, self.altura = nome, x, y, r, altura
        self.cor, self.tipo = cor, tipo

    def contem(self, px, py, folga=0.0):
        return math.hypot(px - self.x, py - self.y) <= self.r + folga

    def raio(self, ox, oy, dx, dy):
        fx, fy = ox - self.x, oy - self.y
        b = fx * dx + fy * dy
        c = fx * fx + fy * fy - self.r * self.r
        if c <= 0:
            return 0.0
        disc = b * b - c
        if disc < 0:
            return None
        t = -b - math.sqrt(disc)
        return t if t >= 0 else None


class Planta:
    def __init__(self, pontos, medidas):
        self.pontos = pontos
        self.medidas = medidas
        s = medidas["salao"]
        self.x_min, self.x_max = s["x_min"], s["x_max"]
        self.y_min, self.y_max = s["y_min"], s["y_max"]
        e, h = s["espessura_parede"], s["altura_parede"]
        largura, altura = self.x_max - self.x_min, self.y_max - self.y_min
        cx, cy = (self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2

        self.paredes = [
            Caixa("parede_norte", cx, self.y_max + e / 2, largura + 2 * e, e, h, cor=COR_PAREDE),
            Caixa("parede_sul", cx, self.y_min - e / 2, largura + 2 * e, e, h, cor=COR_PAREDE),
            Caixa("parede_oeste", self.x_min - e / 2, cy, e, altura, h, cor=COR_PAREDE),
            Caixa("parede_leste", self.x_max + e / 2, cy, e, altura, h, cor=COR_PAREDE),
        ]

        m = medidas["mesa"]
        c = medidas.get("cadeira")
        self.mesas, self.cadeiras = [], []
        for nome, p in sorted(pontos.items(), key=lambda kv: _ordem(kv[0])):
            if not nome.startswith("mesa_"):
                continue
            x, y = _na_frente(p, m["distancia_do_ponto"])
            self.mesas.append(Cilindro(nome, x, y, m["raio"], m["altura"], cor=COR_TAMPO))
            if not c:
                continue
            # cadeiras nos dois lados da mesa, viradas para ela (o robo chega pelo outro lado)
            yaw = p.get("yaw", 0.0)
            lx, ly = -math.sin(yaw), math.cos(yaw)
            for lado, sinal in (("a", 1), ("b", -1)):
                d = sinal * c["distancia_da_mesa"]
                self.cadeiras.append(Caixa("cadeira_%s_%s" % (nome, lado), x + d * lx, y + d * ly,
                                           c["lado"], c["lado"], c["altura_assento"], yaw=yaw - sinal * math.pi / 2,
                                           cor=COR_CADEIRA, tipo="cadeira"))

        b = medidas["bancada"]
        self.bancadas = []
        for nome, p in sorted(pontos.items()):
            if not nome.startswith("estacao_"):
                continue
            x, y = _na_frente(p, b["distancia_do_ponto"])
            # a bancada fica de lado para o robo: o comprimento cruza a direcao do yaw
            yaw = p.get("yaw", 0.0) + math.pi / 2
            cor = COR_BANCADA.get(nome, (0.6, 0.6, 0.6))
            self.bancadas.append(Caixa("bancada_" + nome, x, y, b["comprimento"], b["profundidade"],
                                       b["altura"], yaw=yaw, cor=cor, tipo="bancada"))

    @property
    def moveis(self):
        return self.paredes + self.mesas + self.cadeiras + self.bancadas

    def ocupado(self, x, y, folga=0.0):
        """True se o ponto cai dentro de algum movel ou fora do salao."""
        if not (self.x_min - folga <= x <= self.x_max + folga and self.y_min - folga <= y <= self.y_max + folga):
            return True
        return any(m.contem(x, y, folga) for m in self.moveis)


def _ordem(nome):
    num = nome.split("_")[-1]
    return (nome.split("_")[0], int(num) if num.isdigit() else 0)


def _na_frente(ponto, distancia):
    yaw = ponto.get("yaw", 0.0)
    return ponto["x"] + distancia * math.cos(yaw), ponto["y"] + distancia * math.sin(yaw)


def carregar(pontos_path=PONTOS_PADRAO, medidas_path=MEDIDAS_PADRAO):
    with open(pontos_path) as f:
        pontos = yaml.safe_load(f)["points"]
    with open(medidas_path) as f:
        medidas = yaml.safe_load(f)
    return Planta(pontos, medidas)
