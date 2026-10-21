"""Mapa e planejamento de rota com A*.

Mapa: le um mapa no formato do map_server (.yaml + .pgm), o mesmo que o gmapping
salva com o map_saver. Cada quadradinho vira livre, ocupado ou desconhecido.

Margem de seguranca: para cada quadradinho calculamos a distancia ate o obstaculo
mais perto. Mais perto que o raio do robo = proibido (o robo bateria). Entre o raio
do robo e o "raio de conforto" = permitido, mas mais caro. Assim o A* prefere o
meio dos corredores em vez de raspar nas mesas.

A*: busca em 8 direcoes. Custo de um passo = tamanho do passo x (1 + custo extra
de estar perto de obstaculo). Heuristica = distancia octil ate o destino (nunca
superestima o custo, entao o A* acha o caminho de menor custo).

Obstaculos novos (pessoas, cadeiras fora do lugar) vistos pelo laser podem ser
marcados por alguns segundos; o A* passa a contornar esses pontos (desvio).
"""
import heapq
import math
import os

import yaml

INF = float("inf")
LIVRE, OCUPADO, DESCONHECIDO = 0, 100, 255
RAIZ2 = math.sqrt(2.0)


def ler_pgm(caminho):
    """Le uma imagem PGM binaria (P5). Devolve largura, altura, maximo e os bytes."""
    with open(caminho, "rb") as f:
        dados = f.read()
    tokens, pos = [], 0
    while len(tokens) < 4:
        while dados[pos:pos + 1].isspace():
            pos += 1
        if dados[pos:pos + 1] == b"#":
            pos = dados.index(b"\n", pos) + 1
            continue
        fim = pos
        while not dados[fim:fim + 1].isspace():
            fim += 1
        tokens.append(dados[pos:fim])
        pos = fim
    if tokens[0] != b"P5":
        raise ValueError("so sei ler PGM binario (P5): %s" % caminho)
    largura, altura, maximo = int(tokens[1]), int(tokens[2]), int(tokens[3])
    pos += 1  # um espaco em branco depois do cabecalho
    return largura, altura, maximo, dados[pos:pos + largura * altura]


class Mapa:
    def __init__(self, yaml_path):
        with open(yaml_path) as f:
            info = yaml.safe_load(f)
        imagem = info["image"]
        if not os.path.isabs(imagem):
            imagem = os.path.join(os.path.dirname(os.path.abspath(yaml_path)), imagem)
        self.res = float(info["resolution"])
        self.x0, self.y0 = float(info["origin"][0]), float(info["origin"][1])
        negate = int(info.get("negate", 0))
        lim_ocupado = float(info.get("occupied_thresh", 0.65))
        lim_livre = float(info.get("free_thresh", 0.196))

        w, h, maximo, pixels = ler_pgm(imagem)
        self.largura, self.altura = w, h
        # grade[k], k = j * largura + i; j = 0 e a linha de BAIXO do mapa (y menor),
        # ao contrario da imagem, que comeca pela linha de cima
        self.grade = bytearray(w * h)
        for linha in range(h):
            j = h - 1 - linha
            base_img, base = linha * w, j * w
            for i in range(w):
                p = pixels[base_img + i] / maximo
                ocup = p if negate else 1.0 - p
                if ocup > lim_ocupado:
                    self.grade[base + i] = OCUPADO
                elif ocup < lim_livre:
                    self.grade[base + i] = LIVRE
                else:
                    self.grade[base + i] = DESCONHECIDO

    def celula(self, x, y):
        i = int((x - self.x0) / self.res)
        j = int((y - self.y0) / self.res)
        if 0 <= i < self.largura and 0 <= j < self.altura:
            return j * self.largura + i
        return None

    def centro(self, k):
        i, j = k % self.largura, k // self.largura
        return self.x0 + (i + 0.5) * self.res, self.y0 + (j + 0.5) * self.res

    def dados_occupancy_grid(self):
        """Valores no formato do nav_msgs/OccupancyGrid (0 livre, 100 ocupado, -1 desconhecido)."""
        return [-1 if v == DESCONHECIDO else v for v in self.grade]


class Planejador:
    def __init__(self, mapa, raio_robo=0.30, raio_conforto=0.70, peso=3.0, margem_pessoas=0.15):
        self.m = mapa
        self.raio_robo = raio_robo
        self.raio_conforto = max(raio_conforto, raio_robo + mapa.res)
        self.peso = peso
        # obstaculos vistos pelo laser costumam ser pessoas: o robo passa mais longe deles
        self.margem = margem_pessoas
        n = mapa.largura * mapa.altura
        self.dist_est = self._distancias()          # distancia ate o obstaculo do mapa (m)
        self.dist_din = [INF] * n                    # distancia ate obstaculo visto pelo laser (m)
        self.bloq = bytearray(n)                     # 1 = proibido para o centro do robo
        self.extra = [0.0] * n                       # custo extra por estar perto de obstaculo
        for k in range(n):
            self._atualizar(k)
        self.marcas = {}                             # celula marcada -> ate quando vale (s)
        alcance = self.raio_conforto + self.margem
        r = int(math.ceil(alcance / mapa.res))
        self._disco = sorted(
            ((di, dj, math.hypot(di, dj) * mapa.res)
             for di in range(-r, r + 1) for dj in range(-r, r + 1)
             if math.hypot(di, dj) * mapa.res <= alcance),
            key=lambda t: t[2])

    # ------------------------------------------------------------ distancias
    def _distancias(self):
        """Transformada de distancia (chanfro 1 / raiz de 2) em duas passadas."""
        w, h = self.m.largura, self.m.altura
        g = self.m.grade
        d = [0.0 if g[k] != LIVRE else INF for k in range(w * h)]
        for j in range(h):
            for i in range(w):
                k = j * w + i
                v = d[k]
                if v == 0.0:
                    continue
                if i > 0 and d[k - 1] + 1 < v:
                    v = d[k - 1] + 1
                if j > 0:
                    b = k - w
                    if d[b] + 1 < v:
                        v = d[b] + 1
                    if i > 0 and d[b - 1] + RAIZ2 < v:
                        v = d[b - 1] + RAIZ2
                    if i < w - 1 and d[b + 1] + RAIZ2 < v:
                        v = d[b + 1] + RAIZ2
                d[k] = v
        for j in range(h - 1, -1, -1):
            for i in range(w - 1, -1, -1):
                k = j * w + i
                v = d[k]
                if v == 0.0:
                    continue
                if i < w - 1 and d[k + 1] + 1 < v:
                    v = d[k + 1] + 1
                if j < h - 1:
                    c = k + w
                    if d[c] + 1 < v:
                        v = d[c] + 1
                    if i < w - 1 and d[c + 1] + RAIZ2 < v:
                        v = d[c + 1] + RAIZ2
                    if i > 0 and d[c - 1] + RAIZ2 < v:
                        v = d[c - 1] + RAIZ2
                d[k] = v
        res = self.m.res
        return [v * res for v in d]

    def _atualizar(self, k):
        d = min(self.dist_est[k], self.dist_din[k] - self.margem)
        if d < self.raio_robo:
            self.bloq[k], self.extra[k] = 1, 0.0
        elif d < self.raio_conforto:
            f = (self.raio_conforto - d) / (self.raio_conforto - self.raio_robo)
            self.bloq[k], self.extra[k] = 0, self.peso * f * f
        else:
            self.bloq[k], self.extra[k] = 0, 0.0

    def distancia_estatica(self, x, y):
        k = self.m.celula(x, y)
        return 0.0 if k is None else self.dist_est[k]

    def distancia_dinamica(self, x, y):
        k = self.m.celula(x, y)
        return 0.0 if k is None else self.dist_din[k]

    def distancia_obstaculo(self, x, y):
        k = self.m.celula(x, y)
        return 0.0 if k is None else min(self.dist_est[k], self.dist_din[k])

    def livre(self, x, y):
        k = self.m.celula(x, y)
        return k is not None and not self.bloq[k]

    # ------------------------------------------------- obstaculos do laser
    def marcar(self, pontos, agora, validade=20.0):
        """Marca pontos (x, y) vistos pelo laser como obstaculo ate agora + validade."""
        novos = 0
        w, h = self.m.largura, self.m.altura
        for x, y in pontos:
            k = self.m.celula(x, y)
            if k is None:
                continue
            if k in self.marcas:
                self.marcas[k] = agora + validade
                continue
            self.marcas[k] = agora + validade
            novos += 1
            i0, j0 = k % w, k // w
            for di, dj, dist in self._disco:
                i, j = i0 + di, j0 + dj
                if 0 <= i < w and 0 <= j < h:
                    kk = j * w + i
                    if dist < self.dist_din[kk]:
                        self.dist_din[kk] = dist
                        self._atualizar(kk)
        return novos

    def esquecer_vencidos(self, agora):
        vencidos = [k for k, ate in self.marcas.items() if ate <= agora]
        if not vencidos:
            return 0
        for k in vencidos:
            del self.marcas[k]
        self._refazer_marcas()
        return len(vencidos)

    def esquecer(self, celulas):
        """Tira algumas marcas (ex.: o laser olhou e o obstaculo nao esta mais la)."""
        tirou = False
        for k in celulas:
            if self.marcas.pop(k, None) is not None:
                tirou = True
        if tirou:
            self._refazer_marcas()

    def esquecer_tudo(self):
        if self.marcas:
            self.marcas.clear()
            self._refazer_marcas()

    def _refazer_marcas(self):
        restantes = list(self.marcas.items())
        self.marcas.clear()
        for k, d in enumerate(self.dist_din):
            if d < INF:
                self.dist_din[k] = INF
                self._atualizar(k)
        for k, ate in restantes:
            self.marcar([self.m.centro(k)], 0.0, ate)  # vale ate o mesmo instante de antes

    # ------------------------------------------------------------------ A*
    def _livre_mais_perto(self, k, raio):
        w, h = self.m.largura, self.m.altura
        i0, j0 = k % w, k // w
        for di, dj, dist in self._disco:
            if dist > raio:
                break
            i, j = i0 + di, j0 + dj
            if 0 <= i < w and 0 <= j < h and not self.bloq[j * w + i]:
                return j * w + i
        return None

    def planejar(self, inicio, fim):
        """Rota de inicio (x, y) ate fim (x, y): lista de pontos (x, y), ou None."""
        m = self.m
        s, g = m.celula(*inicio), m.celula(*fim)
        if s is None or g is None:
            return None
        if self.bloq[s]:  # robo encostado em algo: comeca do lugar livre mais perto
            s = self._livre_mais_perto(s, 0.6)
        if self.bloq[g]:
            if self.dist_est[g] >= self.raio_robo:  # bloqueado por obstaculo visto pelo laser
                return None  # tem alguem parado no destino: espera sair (nao muda o destino)
            g = self._livre_mais_perto(g, 0.4)  # ponto colado num movel: para um pouco antes
        if s is None or g is None:
            return None

        w, h = m.largura, m.altura
        bloq, extra = self.bloq, self.extra
        gi, gj = g % w, g // w
        vizinhos = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                    (1, 1, RAIZ2), (1, -1, RAIZ2), (-1, 1, RAIZ2), (-1, -1, RAIZ2))
        custo = {s: 0.0}
        veio = {s: -1}
        fila = [(0.0, 0.0, s)]
        achou = False
        while fila:
            _, c, k = heapq.heappop(fila)
            if k == g:
                achou = True
                break
            if c > custo[k]:
                continue
            i, j = k % w, k // w
            for di, dj, passo in vizinhos:
                ni, nj = i + di, j + dj
                if ni < 0 or nj < 0 or ni >= w or nj >= h:
                    continue
                kk = nj * w + ni
                if bloq[kk]:
                    continue
                if di and dj and (bloq[j * w + ni] or bloq[nj * w + i]):
                    continue  # nao corta a quina de um obstaculo na diagonal
                nc = c + passo * (1.0 + extra[kk])
                if nc < custo.get(kk, INF):
                    custo[kk] = nc
                    veio[kk] = k
                    dx, dy = abs(ni - gi), abs(nj - gj)
                    heur = dx + dy + (RAIZ2 - 2.0) * min(dx, dy)
                    heapq.heappush(fila, (nc + heur, nc, kk))
        if not achou:
            return None
        celulas = []
        k = g
        while k != -1:
            celulas.append(k)
            k = veio[k]
        celulas.reverse()
        self.ultimas_expandidas = len(custo)
        pontos = self._suavizar(celulas)
        pontos[0] = tuple(inicio)
        if g == m.celula(*fim):
            pontos[-1] = tuple(fim)
        return pontos

    def _reta_ok(self, a, b, limite):
        (xa, ya), (xb, yb) = self.m.centro(a), self.m.centro(b)
        n = int(math.hypot(xb - xa, yb - ya) / (self.m.res * 0.5)) + 1
        for t in range(n + 1):
            k = self.m.celula(xa + (xb - xa) * t / n, ya + (yb - ya) * t / n)
            if k is None or self.bloq[k] or self.extra[k] > limite:
                return False
        return True

    def _suavizar(self, celulas):
        """Corta caminho em linha reta quando da (sem chegar mais perto dos obstaculos)."""
        if len(celulas) <= 2:
            return [self.m.centro(k) for k in celulas]
        piso = self.peso * 0.15
        saida = [celulas[0]]
        a = 0
        while a < len(celulas) - 1:
            melhor = a + 1
            for b in range(a + 2, len(celulas)):
                limite = max(self.extra[celulas[a]], self.extra[celulas[b]], piso)
                if self._reta_ok(celulas[a], celulas[b], limite):
                    melhor = b
                elif b - melhor > 12:
                    break
            saida.append(celulas[melhor])
            a = melhor
        return [self.m.centro(k) for k in saida]


def comprimento(pontos):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pontos, pontos[1:]))
