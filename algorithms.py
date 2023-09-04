# coding: utf-8
import math
import osmnx as ox
import time
import pickle
import random
from datetime import datetime
import heapq
from haversine import haversine, Unit
import numpy as np
from geopy.geocoders import Nominatim
import requests
import folium
import preprocessing
import pulp
from yandex_geocoder import Client


class Algorithms:


    def __init__(self):
        self.w = 0.010405
        self.dir = "E:\YandexDisk\Another\Diplom\Proizv\program\\"

        self.mainGpickle = "main.pickle"
        self.gatesGpickle = "gates.pickle"

        self.mainGgetnode = "mainGgetnode.pickle"
        self.gatesGgetnode = "gatesGgetnode.pickle"

        self.YANDEX_API_KEY = "c6029cf3-e0b1-4af4-ae0f-c6c13acef087"
        self.client = Client(self.YANDEX_API_KEY)
        self.geolocator = None
        self.preproc = None

        self.inf = 10000000000.0


    def load_G_data(self):
        start_time = time.time()
        self.Gmain = self.load_obj(self.dir + self.mainGpickle)
        print(time.time() - start_time)

        start_time = time.time()
        self.Ggates = self.load_obj(self.dir + self.gatesGpickle)
        print(time.time() - start_time)

        start_time = time.time()
        self.Gmain_comm_arrs = self.load_obj(self.dir + self.mainGgetnode)
        print(time.time() - start_time)

        start_time = time.time()
        self.Ggates_comm_arrs = self.load_obj(self.dir + self.gatesGgetnode)
        print(time.time() - start_time)

        self.geolocator = Nominatim(user_agent="RoutingService")
        self.preproc = preprocessing.Preprocessing()


    def load_obj(self, filepathpickle):
        with open(filepathpickle, 'rb') as f:
            obj = pickle.load(f)
        return obj


    def save_obj(self, obj, filepathpickle):
        with open (filepathpickle, 'wb') as f:
            pickle.dump(obj, f)


    def heur(self, G, n, finish):
        return self.w * haversine((G[0][n][0], G[0][n][1]), (G[0][finish][0], G[0][finish][1]))


    def A_star_mod(self, G, start, finish, heur):
        if start == finish:
            path = []
            path.append(start)
            return path
        nodes = G[0]
        edges = G[1]
        g = {}
        g[start] = 0
        h = []
        heapq.heappush(h, (heur(G, start, finish), start))
        p = {}
        closed = set()
        for i in range(0, len(nodes)):
            try:
                current = heapq.heappop(h)[1]
                if current == finish:
                    break
                if edges[current] == None:
                    closed.add(current)
                    continue
                for v in edges[current]:
                    if v in closed:
                        continue
                    temp_cost = g[current] + edges[current][v]
                    closed.add(current)
                    if temp_cost < g.get(v, math.inf):
                        g[v] = temp_cost
                        p[v] = current
                        heapq.heappush(h, (temp_cost + heur(G, v, finish), v))
            except:
                break
        i = finish
        path = []
        while p[i] != start:
            path.append(i)
            i = p[i]
        path.append(start)
        return path


    def get_node(self, point, common_arr):
        y = point[0]
        x = point[1]
        y_arr = common_arr[1]
        x_arr = common_arr[2]
        id_arr = common_arr[0]
        y_const = np.empty(len(id_arr), dtype=np.float64)
        y_const.fill(y)
        x_const = np.empty(len(id_arr), dtype=np.float64)
        x_const.fill(x)
        y_arr_vect = np.array(y_arr, dtype=np.float64)
        x_arr_vect = np.array(x_arr, dtype=np.float64)
        sub_x_arr = x_arr_vect-x_const
        sub_y_arr = y_arr_vect-y_const
        res_arr = sub_x_arr*sub_x_arr + sub_y_arr*sub_y_arr
        nearest_node_index = np.argmin(res_arr)
        return id_arr[nearest_node_index]


    def get_node_fromDB(self, cursor, coords):
        cursor.execute("SELECT node "
                            "FROM public.addresses "
                            "WHERE coords='{}'".format(str(coords)))
        rec = cursor.fetchall()
        node = int(rec[0][0])
        return node


    def find_route_gates(self, coords, G_main, comm_arr_G_main, G_gates, comm_arr_G_gates, cursor):
        orig = coords[0]
        destin = coords[1]
        sr = []
        if haversine(orig, destin) <= 25:
            orig_node = self.get_node(orig, comm_arr_G_main)
            destin_node = self.get_node(destin, comm_arr_G_main)
            shortest_route = self.A_star_mod(G_main, orig_node, destin_node, self.heur)
            sr.append(shortest_route)
        else:
            start_time = time.time()
            sg = self.get_node(orig, comm_arr_G_gates)

            s = self.get_node_fromDB(cursor, orig)
            print(time.time() - start_time, ' s и sg')

            start_time = time.time()
            fg = self.get_node(destin, comm_arr_G_gates)

            f = self.get_node_fromDB(cursor, destin)
            print(time.time() - start_time, ' f и fg')

            start_time = time.time()
            sr_ssg = self.A_star_mod(G_main, s, sg, self.heur)
            print(time.time() - start_time, ' путь s - sg')

            start_time = time.time()
            sr_sgfg = self.A_star_mod(G_gates, sg, fg, self.heur)
            print(time.time() - start_time, ' путь sg - fg')

            start_time = time.time()
            sr_fgf = self.A_star_mod(G_main, fg, f, self.heur)
            print(time.time() - start_time, ' путь fg - f')

            sr.append(sr_ssg)
            sr.append(sr_sgfg)
            sr.append(sr_fgf)
        r = []
        for s in sr:
            rc = self.nodes_to_coords(G_main, s)
            r.append(rc)
        return r


    def getDistance(self, p1, p2, n):
        return self.truncate(haversine(p1.coords, p2.coords), n)


    def clasterization(self, vehicles, warehouses):
        clusters = {}
        for w in warehouses:
            l = np.array([])
            for v in vehicles:
                l = np.append(l, self.getDistance(w, v, 5))
            i_min_list = np.where(l == l.min())
            if i_min_list[0].size == 1:
                if clusters.get(vehicles[i_min_list[0][0]], None) == None:
                    clusters[vehicles[i_min_list[0][0]]] = []
                clusters[vehicles[i_min_list[0][0]]].append(w)
            else:
                i = random.randint(0, i_min_list[0].size - 1)
                if clusters.get(vehicles[i_min_list[0][i]], None) == None:
                    clusters[vehicles[i_min_list[0][i]]] = []
                clusters[vehicles[i_min_list[0][i]]].append(w)
        return clusters


    def findOptimalOrder(self, p, mode):
        if mode == 'finish':
            if len(p) == 2:
                res = [p[0], p[1]]
                return res
            if len(p) == 3:
                res = [p[0], p[1], p[2]]
                return res

            c = []
            n = len(p) + 1

            l = []
            for column in range(1, n - 2):
                l.append(self.getDistance(p[0], p[column], 3))
            l = [0.0] + l + [self.inf]*2
            c.append(l)
            for i in range(1, n-2):
                l = []
                for column in range(1, n-1):
                    if i == column:
                        l.append(0.0)
                    else:
                        l.append(self.getDistance(p[i], p[column], 3))
                l = [self.inf] + l + [self.inf]
                c.append(l)
            l = [self.inf]*(n-2) + [0.0] + [0.0]
            c.append(l)
            l = [0.0] + [self.inf]*(n-2) + [0.0]
            c.append(l)

            x = []
            for i in range(n):
                l = []
                for column in range(n):
                    if i == column:
                        l.append(0.0)
                        continue
                    varx =  pulp.LpVariable(f'x{i}_{column}', cat ='Binary')
                    l.append(varx)
                x.append(l)

            t = pulp.LpVariable.dicts("t", (i for i in range(n)), lowBound=1, upBound=n, cat='Continuous')

            self.problem = pulp.LpProblem('order', pulp.LpMinimize)

            s = []
            for i in range(0, n):
                for column in range(0, n):
                    if i == column:
                        continue
                    s.append(x[i][column] * c[i][column])
            self.problem += pulp.lpSum(s)

            for column in range(0, n):
                a = []
                for i in range(0, n):
                    if i == column:
                        continue
                    a.append(x[i][column])
                    a.append(-x[column][i])
                self.problem += pulp.lpSum(a) == 0

            for column in range(1, n):
                a = []
                for i in range(0, n):
                    if i == column:
                        continue
                    a.append(x[i][column])
                self.problem += pulp.lpSum(a) == 1

            self.problem += pulp.lpSum([x[0][j] for j in range(1, n)]) == 1

            for i in range(n):
                for column in range(n):
                    if i != column and (i != 0 and column != 0):
                        self.problem += t[column] >= t[i] + 1 - (2 * n) * (1 - x[i][column])

            self.problem.solve()

            res = [p[0]]
            current_line = 0
            while current_line != n - 2:
                for column in range(n):
                    if pulp.value(x[current_line][column]) == 1:
                        current_line = column
                        res.append(p[column])
                        break
            return res
        else:
            if len(p) == 2:
                res = [p[0], p[1], p[0]]
                return res

            c = []
            n = len(p)

            for row in range(n):
                l = []
                for col in range(n):
                    if row == col:
                        l.append(0.0)
                        continue
                    l.append(self.getDistance(p[row], p[col], 3))
                c.append(l)

            x = []
            for i in range(n):
                l = []
                for column in range(n):
                    if i == column:
                        l.append(0.0)
                        continue
                    varx = pulp.LpVariable(f'x{i}_{column}', cat='Binary')
                    l.append(varx)
                x.append(l)

            t = pulp.LpVariable.dicts("t", (i for i in range(n)), lowBound=1, upBound=n, cat='Continuous')

            self.problem = pulp.LpProblem('order', pulp.LpMinimize)

            s = []
            for i in range(0, n):
                for column in range(0, n):
                    if i == column:
                        continue
                    s.append(x[i][column] * c[i][column])
            self.problem += pulp.lpSum(s)

            for column in range(0, n):
                a = []
                for i in range(0, n):
                    if i == column:
                        continue
                    a.append(x[i][column])
                    a.append(-x[column][i])
                self.problem += pulp.lpSum(a) == 0

            for column in range(1, n):
                a = []
                for i in range(0, n):
                    if i == column:
                        continue
                    a.append(x[i][column])
                self.problem += pulp.lpSum(a) == 1

            self.problem += pulp.lpSum([x[0][j] for j in range(1, n)]) == 1

            for i in range(n):
                for column in range(n):
                    if i != column and (i != 0 and column != 0):
                        self.problem += t[column] >= t[i] + 1 - (2 * n) * (1 - x[i][column])

            self.problem += pulp.lpSum([x[i][i] for i in range(0, n)]) == 0

            self.problem.solve()

            checkres = []
            for i in range(n):
                l = []
                for j in range(n):
                    if i == j:
                        l.append(0)
                        continue
                    l.append(pulp.value(x[i][j]))
                checkres.append(l)

            checkt = []
            for i in range(n):
                checkt.append(pulp.value(t[i]))

            res = [p[0]]
            current_line = 0
            while True:
                for column in range(n):
                    if pulp.value(x[current_line][column]) == 1:
                        current_line = column
                        res.append(p[column])
                        break
                if current_line == 0: break
            return res


    def getValidPoints(self, points, T, V):
        res = []
        xtarr = []
        tarr = []
        xvarr = []
        varr = []
        for i in range(len(points)):
            x = pulp.LpVariable(f'x{i}', cat =pulp.LpBinary)
            xvarr.append(x)
            x = pulp.LpVariable(f'x{i}', cat=pulp.LpBinary)
            xtarr.append(x)
            tarr.append(points[i].t)
            varr.append(points[i].v)
        self.problemT = pulp.LpProblem('getValidPointsTonnage', pulp.LpMaximize)
        self.problemT += pulp.lpSum([x * t for x, t in zip(xtarr, tarr)])
        self.problemT += pulp.lpSum([x * t for x, t in zip(xtarr, tarr)]) <= T
        self.problemT.solve()

        self.problemV = pulp.LpProblem('getValidPointsValue', pulp.LpMaximize)
        self.problemV += pulp.lpSum([x * v for x, v in zip(xvarr, varr)])
        self.problemV += pulp.lpSum([x * v for x, v in zip(xvarr, varr)]) <= V
        self.problemV.solve()

        for i in range(len(points)):
            if pulp.value(xtarr[i]) == 1 and pulp.value(xvarr[i]) == 1:
                res.append(points[i])
        return res


    def drawMarkers(self, orders, map):
        vehicles = orders.vehicles
        warehouses = orders.warehouses
        clients = orders.clients
        finishes = orders.finishes

        for i in range(len(vehicles)):
            coords = self.getRandCoords(vehicles[i].coords)
            vehicles[i].dc = coords
            folium.Marker(
                location=[coords[0], coords[1]],
                tooltip=f'Машина ({vehicles[i].id})',
                icon=folium.Icon(color="red")).add_to(map)

        for i in range(len(warehouses)):
            coords = self.getRandCoords(warehouses[i].coords)
            warehouses[i].dc = coords
            folium.Marker(
                location=[coords[0], coords[1]],
                tooltip=f'Склад ({warehouses[i].id})',
                icon=folium.Icon(color="green")).add_to(map)

        for w in clients:
            c = clients[w]
            for i in range(len(c)):
                coords = self.getRandCoords(c[i].coords)
                c[i].dc = coords
                folium.Marker(
                    location=[coords[0], coords[1]],
                    tooltip=f'Клиент ({c[i].id}) склада ({w.id})',
                    icon=folium.Icon(color="blue")).add_to(map)

        for v in finishes:
            coords = self.getRandCoords(finishes[v].coords)
            finishes[v].dc = coords
            folium.Marker(
                location=[coords[0], coords[1]],
                tooltip=f'Финиш ({finishes[v].id}) машины ({v.id})',
                icon=folium.Icon(color="orange")).add_to(map)


    def getRandCoords(self, coords):
        circle_r = 100/(1000*haversine((0, 1), (0, 0)))
        circle_x = coords[1]
        circle_y = coords[0]
        alpha = 2 * math.pi * random.random()
        r = circle_r * math.sqrt(random.random())
        x = r * math.cos(alpha) + circle_x
        y = r * math.sin(alpha) + circle_y
        rand_coords = (y, x)
        return rand_coords


    def createArrow(self, coords1, coords2, angle, a, map, color):
        x1 = coords1[1]
        y1 = coords1[0]
        x2 = coords2[1]
        y2 = coords2[0]

        L = haversine(coords1, coords2)

        if L != 0:
            b = (a/1000)/L
        else:
            b = a/1000

        xt = x2 - b * (x2 - x1)
        yt = y2 - b * (y2 - y1)

        f1 = angle * (math.pi / 180)

        x3 = x2 + (xt - x2) * math.cos(f1) - (yt - y2) * math.sin(f1)
        y3 = y2 + (xt - x2) * math.sin(f1) + (yt - y2) * math.cos(f1)

        f2 = (-angle)*(math.pi/180)

        x4 = x2 + (xt - x2) * math.cos(f2) - (yt - y2) * math.sin(f2)
        y4 = y2 + (xt - x2) * math.sin(f2) + (yt - y2) * math.cos(f2)

        c = b * 0.9

        x5 = x2 - c * (x2 - x1)
        y5 = y2 - c * (y2 - y1)

        folium.Polygon([(y4, x4), (y5, x5), (y3, x3), (y2, x2)],
                       weight = 4,
                       color = color,
                       fill_color = color,
                       fill_opacity = 1).add_to(map)


    def findSolutions(self, orders):
        vehicles = orders.vehiclesMutable
        finishes = orders.finishesMutable
        warehouses = orders.warehousesMutable
        clients = orders.clientsMutable

        clusters = self.clasterization(vehicles, warehouses)

        for v in clusters:
            for w in clusters[v]:
                for c in clients[w]:
                    c.vehicle = v

        for w in clients:
            v = clients[w][0].vehicle
            T = v.T
            V = v.V
            validclients = self.getValidPoints(clients[w], T, V)
            clients[w] = validclients
            if len(validclients) == 0:
                clusters[v].remove(w)

        for w in clients:
            if len(clients[w]) != 0:
                res = self.findOptimalOrder([w] + clients[w], 'no_finish')
                i = len(res) - 1
                res = res[1:i]
                clients[w] = res

        solutions = {}
        for v in clusters:
            res = self.findOptimalOrder([v] + clusters[v] + [finishes[v]], 'finish')
            if len(res) > 2:
                i = len(res) - 1
                solutions[v] = res[1:i]
                r = []
                for w in solutions[v]:
                    r += [w] + clients[w]
                solutions[v] = [v] + r + [finishes[v]]
            else:
                solutions[v] = [v] + [finishes[v]]
        return solutions


    def G_to_ev(self, G):
        nodes = {}
        for c, data in G.nodes(data = True):
            a = [0]*2
            a[0] = data['y']
            a[1] = data['x']
            nodes[c] = a
        edges = {}
        for u, v, data in G.edges(data = True):
            du = G[u]
            dv = G[v]
            if v in du:
                if edges.get(u, None) == None:
                    edges[u] = {}
                    edges[u][v] = data['val']
                else:
                    edges[u][v] = data['val']
            if u in dv:
                if edges.get(v, None) == None:
                    edges[v] = {}
                    edges[v][u] = data['val']
                else:
                    edges[v][u] = data['val']
        self.save_obj(nodes, fr'E:\YandexDisk\Другие материалы\Диплом\Производственная практика\program\nodesg.pickle')
        self.save_obj(edges, fr'E:\YandexDisk\Другие материалы\Диплом\Производственная практика\program\edgesg.pickle')


    def calculate_parameter(self, G):
        for u, v, data in G.edges(data=True, keys=False):
            data['val'] = self.truncate(math.sqrt((0 - data['length'])**2 + (1 - data['quality'])**2 + (1 - data['maxspeed'])**2), 9)


    def normalize_data(self, G):
        edgesVals = ox.graph_to_gdfs(G, nodes=False, edges=True)
        maxl = edgesVals['length'].max()
        maxq = edgesVals['quality'].max()
        maxs = edgesVals['maxspeed'].max()

        minl = edgesVals['length'].min()
        minq = edgesVals['quality'].min()
        mins = edgesVals['maxspeed'].min()

        tl = maxl-minl
        bl = minl/tl

        tq = maxq - minq
        bq = minq / tq

        ts = maxs - mins
        bs = mins / ts

        for u, v, data in G.edges(data=True, keys=False):
            data['length'] = self.truncate(data['length']/tl - bl, 9)
            data['quality'] = self.truncate(data['quality'] / tq - bq, 9)
            data['maxspeed'] = self.truncate(data['maxspeed'] / ts - bs, 9)


    def truncate(self, f, n):
        s = "%.20f" % f
        return float(s[:s.find('.') + n + 1])


    def get_cond(self, t):
        random.seed(datetime.now().timestamp())
        best_cond = ['motorway', 'trunk', 'motorway_link', 'trunk_link']
        normal_cond = ['primary', 'secondary', 'primary_link', 'secondary_link']
        average_cond = ['tertiary', 'tertiary_link', 'unclassified']
        bad_cond = ['residential']
        if t in best_cond:
            return self.truncate(random.uniform(0.95, 1), 3)
        elif t in normal_cond:
            return self.truncate(random.uniform(0.8, 0.94999), 3)
        elif t in average_cond:
            return self.truncate(random.uniform(0.4, 0.79999), 3)
        elif t in bad_cond:
            return self.truncate(random.uniform(0, 0.39999), 3)
        else:
            return 1


    def add_new_weights(self, data):
        data['length'] = float(data['length'])
        try:
            if 'maxspeed' not in data:
                data['maxspeed'] = 60
            else:
                data['maxspeed'] = float(data['maxspeed'])
        except:
            data['maxspeed'] = 60
        data['quality'] = self.get_cond(data['highway'])
        data['val'] = 0


    def preproc_G(self, G):
        for u, v, data in G.edges(data=True, keys=False):
            self.add_new_weights(data)
        self.normalize_data(G)
        self.calculate_parameter(G)
        return G


    def conversion_G(self, fGosm, fGp):
        G = ox.graph_from_xml(fr'E:\YandexDisk\Другие материалы\Диплом\Производственная практика\program\{fGosm}', bidirectional = False, simplify=False, retain_all=True)
        self.preproc_G(G)
        self.save_obj(G, fr'E:\YandexDisk\Другие материалы\Диплом\Производственная практика\program\{fGp}')


    def nodes_to_coords(self, G, nodes):
        nds = G[0]
        coords = []
        for n in nodes:
            coords.append((nds[n][0], nds[n][1]))
        return coords


    def adr_to_coords(self, adr):
        coordinates = self.client.coordinates(adr)
        coords = (float(coordinates[1]), float(coordinates[0]))
        return coords


    def find_path(self, solves, cursor):
        res = []
        for v in solves:
            points = solves[v]
            sr = []
            for i in range(len(points) - 1):
                route_coords = self.find_route_gates([points[i].coords, points[i+1].coords], self.Gmain, self.Gmain_comm_arrs, self.Ggates, self.Ggates_comm_arrs, cursor)
                sr = sr + route_coords
            res.append(sr)
        return res