#!/usr/bin/env python3
"""Gerenciador de missões (responsável: Ian) - versão 21/10.

O robô trabalha em VIAGENS, como um garçom de verdade: em vez de levar um
pedido por vez, junta vários pedidos e entrega todos numa volta só.

  1. Pede à fila os pedidos da viagem (/garcom/next_orders): os mais urgentes
     primeiro, até encher a bandeja ou chegar ao limite de mesas.
  2. Soma os itens de todos os pedidos por estação de coleta.
  3. Planeja a rota: a ordem das bancadas e das mesas que dá o menor custo,
     onde custo = soma dos tempos de espera de cada mesa + peso x atraso
     previsto. Assim a rota equilibra a mesa mais perto e a mais atrasada.
     Com até 7 mesas testa todas as ordens possíveis; acima disso, escolhe
     a próxima mesa de menor custo a cada passo.
  4. Passa uma vez em cada bancada (/garcom/pickup_request) e espera a
     confirmação de que a bandeja está pronta (/garcom/pickup_done).
  5. Entrega mesa por mesa e, se houver pedidos esperando, já emenda a
     próxima viagem; se não, volta para a base.

Publica o estado dos pedidos em /garcom/order_status e a viagem planejada
em /garcom/trip.
"""
import copy
import itertools
import math
import threading
from collections import Counter, OrderedDict

import actionlib
import rospy
from garcom_msgs.msg import (GoToPointAction, GoToPointGoal, OrderStatus,
                             PickupDone, PickupLine, PickupRequest, Trip)
from garcom_msgs.srv import NextOrders

EXACT_LIMIT = 7          # até quantas mesas testa todas as ordens possíveis
PICKUP_ESTIMATE_S = 5.0  # tempo estimado para montar a bandeja em cada bancada


class QuietActionClient(actionlib.SimpleActionClient):
    """SimpleActionClient sem o falso erro "transition callback on a goal handle that we're not tracking".

    Quando o servidor responde muito rápido, a primeira transição do novo destino
    pode chegar antes de o actionlib registrar esse destino. Ela é ignorada e as
    transições seguintes chegam normalmente.
    """

    def _handle_transition(self, gh):
        if gh != self.gh:
            return
        super()._handle_transition(gh)


class MissionManager:
    def __init__(self):
        cardapio = rospy.get_param("/garcom/cardapio", [])
        self.station_of = {entry["item"]: entry["estacao"] for entry in cardapio}
        self.points = rospy.get_param("/garcom/points", {})
        self.speed = float(rospy.get_param("/garcom/robot_speed_mps", 1.5))
        self.warning_ratio = float(rospy.get_param("/garcom/warning_ratio", 0.7))

        self.base = rospy.get_param("~base", "base")
        self.capacity = int(rospy.get_param("~bandeja_capacidade", 8))
        self.max_tables = int(rospy.get_param("~max_mesas_por_viagem", 5))
        self.group_wait = float(rospy.get_param("~espera_para_agrupar_s", 4.0))
        self.table_time = float(rospy.get_param("~tempo_na_mesa_s", 2.0))
        self.late_weight = float(rospy.get_param("~peso_do_atraso", 3.0))
        self.pickup_timeout = float(rospy.get_param("~pickup_timeout_s", 60.0))

        self.here = self.base
        self.trip_id = 0
        self.confirmed = set()   # (viagem, estação) confirmados pela tela da bancada
        self.confirm_lock = threading.Condition()

        self.status_pub = rospy.Publisher("/garcom/order_status", OrderStatus, queue_size=50)
        self.pickup_pub = rospy.Publisher("/garcom/pickup_request", PickupRequest, queue_size=10)
        self.trip_pub = rospy.Publisher("/garcom/trip", Trip, queue_size=10, latch=True)
        rospy.Subscriber("/garcom/pickup_done", PickupDone, self.on_pickup_done)

        self.nav = QuietActionClient("/garcom/go_to_point", GoToPointAction)
        rospy.loginfo("Aguardando o servidor de navegação...")
        self.nav.wait_for_server()

        rospy.loginfo("Aguardando a fila de pedidos...")
        rospy.wait_for_service("/garcom/next_orders")
        self.next_orders = rospy.ServiceProxy("/garcom/next_orders", NextOrders)
        rospy.loginfo("Gerenciador de missões pronto (bandeja de %d itens, até %d mesas por viagem).",
                      self.capacity, self.max_tables)

    # ------------------------------------------------------------ apoio
    def on_pickup_done(self, msg):
        with self.confirm_lock:
            self.confirmed.add((msg.trip_id, msg.station))
            self.confirm_lock.notify_all()

    def publish_status(self, order, status, stops_before=0):
        msg = copy.deepcopy(order)
        msg.status = status
        msg.trip_id = self.trip_id
        msg.stops_before = stops_before
        elapsed = (rospy.Time.now() - msg.stamp).to_sec()
        msg.late = elapsed > msg.deadline_s
        msg.warning = msg.late or elapsed >= self.warning_ratio * msg.deadline_s
        self.status_pub.publish(msg)

    def go_to(self, point):
        self.nav.send_goal(GoToPointGoal(point_name=point))
        self.nav.wait_for_result()
        result = self.nav.get_result()
        if result and result.success:
            self.here = point
            return True
        return False

    def travel(self, a, b):
        """Tempo estimado de viagem entre dois pontos (linha reta / velocidade)."""
        pa, pb = self.points.get(a), self.points.get(b)
        if not pa or not pb:
            return 0.0
        return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"]) / self.speed

    # ----------------------------------------------------- planejamento
    def route_cost(self, start, t0, seq, slack, weight):
        """Custo de entregar as mesas na ordem seq, saindo de start no instante t0.

        custo = soma, para cada mesa, de (instante de chegada + peso x atraso previsto),
        multiplicada pelo número de pedidos daquela mesa.
        """
        t, pos, cost = t0, start, 0.0
        for table in seq:
            t += self.travel(pos, table)
            late = max(0.0, t - slack[table])
            cost += weight[table] * (t + self.late_weight * late)
            t += self.table_time
            pos = table
        return cost, t

    def best_route(self, start, t0, tables, slack, weight):
        if len(tables) <= EXACT_LIMIT:
            seqs = itertools.permutations(tables)
            return min(((list(s),) + self.route_cost(start, t0, s, slack, weight) for s in seqs),
                       key=lambda r: r[1])
        # muitas mesas: escolhe a próxima de menor custo a cada passo
        seq, left, pos, t = [], set(tables), start, t0
        while left:
            nxt = min(left, key=lambda m: self.route_cost(pos, t, [m], slack, weight)[0])
            t = self.route_cost(pos, t, [nxt], slack, weight)[1]
            seq.append(nxt)
            left.remove(nxt)
            pos = nxt
        return (seq,) + self.route_cost(start, t0, seq, slack, weight)

    def plan_trip(self, orders, stations):
        """Escolhe a ordem das bancadas e das mesas. Devolve (bancadas, mesas, custo, tempo, custo_fifo)."""
        now = rospy.Time.now()
        slack, weight, first_seen = {}, Counter(), []
        for o in sorted(orders, key=lambda o: o.id):
            table = "mesa_%d" % o.table_id
            remaining = o.deadline_s - (now - o.stamp).to_sec()
            slack[table] = min(slack.get(table, math.inf), remaining)
            weight[table] += 1
            if table not in first_seen:
                first_seen.append(table)

        best = None
        for st_seq in itertools.permutations(stations):
            t, pos = 0.0, self.here
            for st in st_seq:
                t += self.travel(pos, st) + PICKUP_ESTIMATE_S
                pos = st
            seq, cost, total = self.best_route(pos, t, list(slack), slack, weight)
            if best is None or cost < best[2]:
                fifo_cost = self.route_cost(pos, t, first_seen, slack, weight)[0]
                best = (list(st_seq), seq, cost, total, fifo_cost)
        return best

    # ------------------------------------------------------------ coleta
    def collect(self, station, totals, lines):
        """Pede a coleta na bancada e espera a confirmação."""
        key = (self.trip_id, station)
        self.pickup_pub.publish(PickupRequest(
            trip_id=self.trip_id, station=station,
            items=list(totals.keys()), quantities=list(totals.values()), lines=lines))

        deadline = rospy.Time.now() + rospy.Duration(self.pickup_timeout)
        with self.confirm_lock:
            while key not in self.confirmed and not rospy.is_shutdown():
                left = (deadline - rospy.Time.now()).to_sec()
                if left <= 0:
                    break
                self.confirm_lock.wait(min(left, 0.5))
            ok = key in self.confirmed
            self.confirmed.discard(key)
        return ok

    # ------------------------------------------------------------ viagem
    def execute_trip(self, orders):
        self.trip_id += 1

        # itens de cada estação: total e divisão por pedido
        totals = OrderedDict()
        per_order = OrderedDict()
        for o in orders:
            for item in o.items:
                station = self.station_of.get(item)
                if station is None:
                    rospy.logwarn("Item '%s' não está no cardápio; ignorado", item)
                    continue
                totals.setdefault(station, Counter())[item] += 1
                per_order.setdefault(station, OrderedDict()).setdefault(o.id, (o, Counter()))[1][item] += 1

        stations, tables, cost, estimated, fifo_cost = self.plan_trip(orders, list(totals))
        stops = stations + tables
        trip = Trip(trip_id=self.trip_id, stops=stops, current=-1, finished=False,
                    order_ids=[o.id for o in orders], estimated_s=estimated)
        self.trip_pub.publish(trip)

        n_items = sum(len(o.items) for o in orders)
        rospy.loginfo("Viagem %d: %d pedido(s), %d item(ns). Rota: %s. Tempo estimado: %.0f s",
                      self.trip_id, len(orders), n_items, " -> ".join(stops), estimated)
        if len(tables) > 1:
            rospy.loginfo("Viagem %d: custo da rota escolhida %.0f; na ordem de chegada seria %.0f",
                          self.trip_id, cost, fifo_cost)

        for o in orders:
            self.publish_status(o, OrderStatus.EM_COLETA)

        # bancadas
        for idx, station in enumerate(stations):
            trip.current = idx
            self.trip_pub.publish(trip)
            if not self.go_to(station):
                rospy.logerr("Não foi possível chegar em %s", station)
                continue  # TODO(Ian, 23/11): tratamento de falhas
            lines = [PickupLine(order_id=o.id, table_id=o.table_id,
                                items=list(c.keys()), quantities=list(c.values()))
                     for o, c in per_order[station].values()]
            text = ", ".join("%dx %s" % (q, i) for i, q in totals[station].items())
            if self.collect(station, totals[station], lines):
                rospy.loginfo("Viagem %d: coleta confirmada em %s: %s", self.trip_id, station, text)
            else:
                rospy.logwarn("Viagem %d: coleta em %s não confirmada em %.0f s; seguindo assim mesmo",
                              self.trip_id, station, self.pickup_timeout)

        # mesas
        by_table = OrderedDict((t, [o for o in orders if "mesa_%d" % o.table_id == t]) for t in tables)
        for k, table in enumerate(tables):
            for later_k, later in enumerate(tables[k:]):
                for o in by_table[later]:
                    self.publish_status(o, OrderStatus.EM_ENTREGA, stops_before=later_k)
            trip.current = len(stations) + k
            self.trip_pub.publish(trip)
            if not self.go_to(table):
                rospy.logerr("Não foi possível chegar na %s", table)
                continue
            rospy.sleep(self.table_time)  # cliente pegando o pedido
            for o in by_table[table]:
                self.publish_status(o, OrderStatus.ENTREGUE)
                rospy.loginfo("Pedido %d entregue na %s", o.id, table)

        trip.finished = True
        trip.current = len(stops)
        self.trip_pub.publish(trip)

    # ------------------------------------------------------------- laço
    def waiting(self):
        try:
            return self.next_orders(max_items=0, max_tables=0, take=False).waiting
        except rospy.ServiceException as err:
            rospy.logwarn("Fila indisponível: %s", err)
            return 0

    def run(self):
        rate = rospy.Rate(2.0)
        while not rospy.is_shutdown():
            if not self.waiting():
                if self.here != self.base:
                    self.go_to(self.base)
                rate.sleep()
                continue
            if self.here == self.base and self.group_wait > 0:
                rospy.sleep(self.group_wait)  # junta pedidos que chegam quase juntos
            try:
                resp = self.next_orders(max_items=self.capacity, max_tables=self.max_tables, take=True)
            except rospy.ServiceException as err:
                rospy.logwarn("Fila indisponível: %s", err)
                continue
            if resp.orders:
                self.execute_trip(resp.orders)


def main():
    rospy.init_node("mission_manager")
    MissionManager().run()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
