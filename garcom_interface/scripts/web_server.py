#!/usr/bin/env python3
"""Telas web do restaurante (responsável: Ian) - versão 19/10.

Liga o ROS ao navegador. Abra no navegador do mesmo computador:
- http://localhost:8080/mesa?mesa=2  tela da mesa: o cliente escolhe os itens,
  faz o pedido e acompanha o robô até a mesa;
- http://localhost:8080/bancada      tela da bancada: o funcionário vê o que
  colocar na bandeja, confirma a coleta e ajusta o estoque.
  (?estacao=estacao_cafe mostra só os pedidos daquela estação)

Por baixo, o nó publica em /garcom/orders e /garcom/pickup_done, escuta
/garcom/order_status, /garcom/pickup_request e /garcom/stock, e usa o serviço
/garcom/set_stock. As páginas ficam na pasta web/ deste pacote.
"""
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import rospkg
import rospy
from garcom_msgs.msg import Order, OrderStatus, PickupDone, PickupRequest, StockLevels
from garcom_msgs.srv import SetStock

STATUS_KEYS = {
    OrderStatus.RECEBIDO: "recebido",
    OrderStatus.VALIDADO: "validado",
    OrderStatus.EM_COLETA: "em_coleta",
    OrderStatus.EM_ENTREGA: "em_entrega",
    OrderStatus.ENTREGUE: "entregue",
    OrderStatus.RECUSADO: "recusado",
}
MAX_ORDERS = 60   # quantos pedidos a tela guarda


class Bridge:
    """Guarda o estado que as telas mostram e fala com o ROS."""

    def __init__(self):
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.menu = [{
            "item": e["item"],
            "nome": e["nome"],
            "icone": e.get("icone", ""),
            "preco": float(e.get("preco", 0.0)),
            "estacao": e["estacao"],
        } for e in cardapio]
        self.items = {m["item"] for m in self.menu}
        self.stations = rospy.get_param("/garcom/estacoes", {})
        self.tables = int(rospy.get_param("~tables", 4))

        self.lock = threading.Lock()
        self.stock = {}
        self.orders = {}     # id -> dicionário com o último estado
        self.pickups = []    # coletas esperando confirmação

        self.order_pub = rospy.Publisher("/garcom/orders", Order, queue_size=10)
        self.done_pub = rospy.Publisher("/garcom/pickup_done", PickupDone, queue_size=10)
        rospy.Subscriber("/garcom/stock", StockLevels, self.on_stock)
        rospy.Subscriber("/garcom/order_status", OrderStatus, self.on_status)
        rospy.Subscriber("/garcom/pickup_request", PickupRequest, self.on_pickup)
        self.set_stock_srv = rospy.ServiceProxy("/garcom/set_stock", SetStock)

    # ---------------------------------------------------------------- ROS
    def on_stock(self, msg):
        with self.lock:
            self.stock = dict(zip(msg.items, msg.quantities))

    def on_status(self, msg):
        with self.lock:
            old = self.orders.get(msg.id)
            if old and old["status_num"] > msg.status:
                return  # mensagem atrasada; o estado só avança
            self.orders[msg.id] = {
                "id": msg.id,
                "mesa": msg.table_id,
                "itens": list(msg.items),
                "status_num": msg.status,
                "status": STATUS_KEYS.get(msg.status, "?"),
                "stamp": msg.stamp.to_sec(),
                "prazo_s": msg.deadline_s,
                "alerta": msg.warning,
                "atrasado": msg.late,
                "fim": rospy.Time.now().to_sec() if msg.status in (OrderStatus.ENTREGUE, OrderStatus.RECUSADO) else None,
            }
            if len(self.orders) > MAX_ORDERS:
                for oid in sorted(self.orders)[:len(self.orders) - MAX_ORDERS]:
                    del self.orders[oid]
            if msg.status in (OrderStatus.ENTREGUE, OrderStatus.RECUSADO):
                self.pickups = [p for p in self.pickups if p["pedido"] != msg.id]

    def on_pickup(self, msg):
        entry = {
            "pedido": msg.order_id,
            "mesa": msg.table_id,
            "estacao": msg.station,
            "estacao_nome": self.stations.get(msg.station, msg.station),
            "itens": [{"item": i, "qtd": q} for i, q in zip(msg.items, msg.quantities)],
            "desde": rospy.Time.now().to_sec(),
        }
        with self.lock:
            if not any(p["pedido"] == msg.order_id and p["estacao"] == msg.station for p in self.pickups):
                self.pickups.append(entry)

    # ------------------------------------------------------------ ações
    def state(self):
        now = rospy.Time.now().to_sec()
        with self.lock:
            orders = []
            for o in sorted(self.orders.values(), key=lambda o: o["id"], reverse=True):
                o = dict(o)
                o["decorrido_s"] = round((o["fim"] or now) - o["stamp"], 1)
                orders.append(o)
            return {
                "agora": now,
                "mesas": self.tables,
                "cardapio": [dict(m, estoque=self.stock.get(m["item"])) for m in self.menu],
                "estacoes": self.stations,
                "pedidos": orders,
                "coletas": [dict(p, esperando_s=round(now - p["desde"], 1)) for p in self.pickups],
            }

    def place_order(self, mesa, itens):
        if not isinstance(mesa, int) or not 1 <= mesa <= self.tables:
            raise ValueError("Escolha uma mesa de 1 a %d." % self.tables)
        if not isinstance(itens, dict) or not itens:
            raise ValueError("Escolha pelo menos um item.")
        items = []
        for item, qty in itens.items():
            if item not in self.items or not isinstance(qty, int) or not 0 <= qty <= 20:
                raise ValueError("Item inválido: %s" % item)
            items += [item] * qty
        if not items:
            raise ValueError("Escolha pelo menos um item.")
        with self.lock:
            order_id = int(rospy.get_param("/garcom/last_order_id", 0)) + 1
            rospy.set_param("/garcom/last_order_id", order_id)
        self.order_pub.publish(Order(id=order_id, table_id=mesa, items=items, stamp=rospy.Time.now()))
        rospy.loginfo("Pedido %d feito pela tela da mesa %d", order_id, mesa)
        return order_id

    def confirm_pickup(self, pedido, estacao):
        with self.lock:
            before = len(self.pickups)
            self.pickups = [p for p in self.pickups if not (p["pedido"] == pedido and p["estacao"] == estacao)]
            found = len(self.pickups) < before
        if not found:
            raise ValueError("Essa coleta já foi confirmada.")
        self.done_pub.publish(PickupDone(order_id=pedido, station=estacao))
        rospy.loginfo("Bandeja pronta: pedido %d em %s (tela da bancada)", pedido, estacao)

    def set_stock(self, item, quantidade):
        if item not in self.items or not isinstance(quantidade, int) or quantidade < 0:
            raise ValueError("Quantidade inválida para %s." % item)
        resp = self.set_stock_srv(item=item, quantity=quantidade)
        if not resp.success:
            raise ValueError(resp.message)
        return resp.total


def make_handler(bridge, web_dir):
    pages = {"/": "index.html", "/mesa": "mesa.html", "/bancada": "bancada.html"}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)

        def log_message(self, *_args):
            pass  # sem poluir o terminal do ROS

        def send_json(self, data, code=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/estado":
                return self.send_json(bridge.state())
            if path in pages:
                self.path = "/" + pages[path]
            return super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                size = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(size) or b"{}")
                if path == "/api/pedido":
                    return self.send_json({"pedido": bridge.place_order(data.get("mesa"), data.get("itens"))})
                if path == "/api/bandeja_pronta":
                    bridge.confirm_pickup(int(data.get("pedido")), str(data.get("estacao")))
                    return self.send_json({"ok": True})
                if path == "/api/estoque":
                    total = bridge.set_stock(data.get("item"), data.get("quantidade"))
                    return self.send_json({"ok": True, "total": total})
                return self.send_json({"erro": "Endereço não encontrado."}, 404)
            except (ValueError, TypeError) as err:
                return self.send_json({"erro": str(err)}, 400)
            except rospy.ServiceException:
                return self.send_json({"erro": "O estoque não respondeu. Confira se o sistema está rodando."}, 503)

    return Handler


def main():
    rospy.init_node("web_server")
    port = int(rospy.get_param("~port", 8080))
    web_dir = os.path.join(rospkg.RosPack().get_path("garcom_interface"), "web")
    bridge = Bridge()
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(bridge, web_dir))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    rospy.loginfo("Telas prontas: http://localhost:%d/mesa?mesa=1 e http://localhost:%d/bancada", port, port)
    rospy.spin()
    server.shutdown()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
