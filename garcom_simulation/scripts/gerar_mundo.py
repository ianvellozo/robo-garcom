#!/usr/bin/env python3
"""Gera o mundo do Gazebo e o mapa da navegacao a partir da planta do restaurante.

Le:      garcom_navigation/config/pontos.yaml       (onde ficam base, bancadas e mesas)
         garcom_simulation/config/restaurante.yaml  (medidas do salao e dos moveis)
Escreve: garcom_simulation/worlds/restaurante.world (mundo do Gazebo)
         garcom_navigation/maps/restaurante.pgm e .yaml (mapa no formato do map_server)

Uso: rosrun garcom_simulation gerar_mundo.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import restaurante  # noqa: E402

LIVRE, OCUPADO, DESCONHECIDO = 254, 0, 205


def _cor(c):
    return "%.2f %.2f %.2f 1" % c


def _material(cor):
    return ("<material><ambient>%s</ambient><diffuse>%s</diffuse>"
            "<specular>0.1 0.1 0.1 1</specular></material>" % (_cor(cor), _cor(cor)))


def _box(size):
    return "<geometry><box><size>%.3f %.3f %.3f</size></box></geometry>" % size


def _cyl(r, h):
    return "<geometry><cylinder><radius>%.3f</radius><length>%.3f</length></cylinder></geometry>" % (r, h)


def modelo_caixa(c):
    geo = _box((c.sx, c.sy, c.sz))
    return f"""
    <model name="{c.nome}">
      <static>true</static>
      <pose>{c.x:.3f} {c.y:.3f} 0 0 0 {c.yaw:.4f}</pose>
      <link name="link">
        <collision name="colisao"><pose>0 0 {c.sz / 2:.3f} 0 0 0</pose>{geo}</collision>
        <visual name="visual"><pose>0 0 {c.sz / 2:.3f} 0 0 0</pose>{geo}{_material(c.cor)}</visual>
      </link>
    </model>"""


def modelo_mesa(m):
    # mesa redonda com toalha ate o chao: o laser enxerga a mesa inteira
    return f"""
    <model name="{m.nome}">
      <static>true</static>
      <pose>{m.x:.3f} {m.y:.3f} 0 0 0 0</pose>
      <link name="link">
        <collision name="colisao"><pose>0 0 {m.altura / 2:.3f} 0 0 0</pose>{_cyl(m.r, m.altura)}</collision>
        <visual name="toalha"><pose>0 0 {(m.altura - 0.03) / 2:.3f} 0 0 0</pose>{_cyl(m.r, m.altura - 0.03)}{_material(m.cor)}</visual>
        <visual name="tampo"><pose>0 0 {m.altura - 0.015:.3f} 0 0 0</pose>{_cyl(m.r + 0.02, 0.03)}{_material(restaurante.COR_PE)}</visual>
      </link>
    </model>"""


def modelo_cadeira(c, medidas):
    # assento + encosto; a colisao e um bloco so (o laser enxerga a cadeira inteira)
    lado, h, hb = c.sx, medidas["altura_assento"], medidas["altura_encosto"]
    assento = _box((lado, lado, h))
    encosto = _box((0.05, lado, hb - h))
    return f"""
    <model name="{c.nome}">
      <static>true</static>
      <pose>{c.x:.3f} {c.y:.3f} 0 0 0 {c.yaw:.4f}</pose>
      <link name="link">
        <collision name="colisao"><pose>0 0 {h / 2:.3f} 0 0 0</pose>{assento}</collision>
        <visual name="assento"><pose>0 0 {h / 2:.3f} 0 0 0</pose>{assento}{_material(c.cor)}</visual>
        <visual name="encosto"><pose>{-lado / 2 + 0.025:.3f} 0 {(h + hb) / 2:.3f} 0 0 0</pose>{encosto}{_material(c.cor)}</visual>
      </link>
    </model>"""


def modelo_doca(p):
    # marca amarela no chao onde o robo espera (sem colisao)
    return f"""
    <model name="base_do_robo">
      <static>true</static>
      <pose>{p['x']:.3f} {p['y']:.3f} 0.002 0 0 0</pose>
      <link name="link">
        <visual name="marca">{_box((0.7, 0.7, 0.004))}{_material((0.95, 0.69, 0.12))}</visual>
      </link>
    </model>"""


def mundo(planta):
    s = planta.medidas["salao"]
    largura = s["x_max"] - s["x_min"]
    altura = s["y_max"] - s["y_min"]
    cx, cy = (s["x_min"] + s["x_max"]) / 2, (s["y_min"] + s["y_max"]) / 2
    partes = [modelo_caixa(c) for c in planta.paredes]
    partes += [modelo_mesa(m) for m in planta.mesas]
    partes += [modelo_cadeira(c, planta.medidas["cadeira"]) for c in planta.cadeiras]
    partes += [modelo_caixa(b) for b in planta.bancadas]
    if "base" in planta.pontos:
        partes.append(modelo_doca(planta.pontos["base"]))
    piso = f"""
    <model name="piso">
      <static>true</static>
      <pose>{cx:.3f} {cy:.3f} 0.001 0 0 0</pose>
      <link name="link">
        <visual name="visual">{_box((largura, altura, 0.002))}{_material((0.80, 0.76, 0.70))}</visual>
      </link>
    </model>"""
    camera = f"{cx:.2f} {s['y_min'] - 6.5:.2f} 9.5 0 0.85 1.5708"
    return f"""<?xml version="1.0"?>
<!-- Gerado por garcom_simulation/scripts/gerar_mundo.py. Nao edite a mao:
     mude o pontos.yaml ou o restaurante.yaml e rode o gerar_mundo.py de novo. -->
<sdf version="1.6">
  <world name="restaurante">
    <include><uri>model://sun</uri></include>
    <include><uri>model://ground_plane</uri></include>
    <scene>
      <ambient>0.6 0.6 0.6 1</ambient>
      <background>0.84 0.93 0.89 1</background>
      <shadows>false</shadows>
    </scene>
    <physics type="ode">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1</real_time_factor>
      <real_time_update_rate>1000</real_time_update_rate>
    </physics>
    <gui>
      <camera name="user_camera"><pose>{camera}</pose></camera>
    </gui>{piso}{''.join(partes)}
  </world>
</sdf>
"""


def mapa(planta):
    """Rasteriza a planta: cada quadradinho vira livre, ocupado ou desconhecido."""
    res = planta.medidas["mapa"]["resolucao"]
    margem = planta.medidas["mapa"]["margem"]
    e = planta.medidas["salao"]["espessura_parede"]
    x0 = planta.x_min - e - margem
    y0 = planta.y_min - e - margem
    largura = int(math.ceil((planta.x_max + e + margem - x0) / res))
    altura = int(math.ceil((planta.y_max + e + margem - y0) / res))
    moveis = planta.moveis
    meia = res / 2 * 0.999  # meio quadradinho (um pouco menos, para nao empatar na borda)
    linhas = []
    for j in range(altura - 1, -1, -1):  # a primeira linha da imagem e o topo do mapa
        y = y0 + (j + 0.5) * res
        linha = bytearray(largura)
        for i in range(largura):
            x = x0 + (i + 0.5) * res
            if any(m.contem(x, y, meia) for m in moveis):
                linha[i] = OCUPADO
            elif planta.x_min <= x <= planta.x_max and planta.y_min <= y <= planta.y_max:
                linha[i] = LIVRE
            else:
                linha[i] = DESCONHECIDO
        linhas.append(bytes(linha))
    return largura, altura, (x0, y0), res, b"".join(linhas)


def main():
    planta = restaurante.carregar()
    world_path = os.path.join(restaurante.PACOTE, "worlds", "restaurante.world")
    maps_dir = os.path.join(restaurante.REPO, "garcom_navigation", "maps")
    os.makedirs(os.path.dirname(world_path), exist_ok=True)
    os.makedirs(maps_dir, exist_ok=True)

    with open(world_path, "w") as f:
        f.write(mundo(planta))

    largura, altura, (x0, y0), res, dados = mapa(planta)
    with open(os.path.join(maps_dir, "restaurante.pgm"), "wb") as f:
        f.write(b"P5\n# Robo Garcom: restaurante\n%d %d\n255\n" % (largura, altura))
        f.write(dados)
    with open(os.path.join(maps_dir, "restaurante.yaml"), "w") as f:
        f.write("# Gerado por garcom_simulation/scripts/gerar_mundo.py (formato do map_server)\n")
        f.write("image: restaurante.pgm\n")
        f.write("resolution: %.3f\n" % res)
        f.write("origin: [%.3f, %.3f, 0.0]\n" % (x0, y0))
        f.write("negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n")

    print("Mundo: %s (%d mesas, %d cadeiras, %d bancadas)" % (world_path, len(planta.mesas), len(planta.cadeiras), len(planta.bancadas)))
    print("Mapa:  %s/restaurante.pgm (%d x %d quadradinhos de %.0f cm)" % (maps_dir, largura, altura, res * 100))


if __name__ == "__main__":
    main()
