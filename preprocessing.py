# coding: utf-8
import math
import osmnx as ox
import pickle
import random
from datetime import datetime


class Preprocessing:


    def __init__(self):
        self.dir = "E:\YandexDisk\Another\Diplom\Proizv\program\\"

        self.mainGpickle = "mainG.pickle"
        self.gatesGpickle = "gatesG.pickle"

        self.mainGgetnode = "mainGgetnode.pickle"
        self.gatesGgetnode = "gatesGgetnode.pickle"

        self.YANDEX_API_KEY = "c6029cf3-e0b1-4af4-ae0f-c6c13acef087"
        self.geolocator = None


    def load_obj(self, filepathpickle):
        with open(filepathpickle, 'rb') as f:
            obj = pickle.load(f)
        return obj


    def save_obj(self, obj, filepathpickle):
        with open (filepathpickle, 'wb') as f:
            pickle.dump(obj, f)


    def G_to_Gform(self, G, filename):
        Gform = [0]*2
        nodes = {}
        for c, data in G.nodes(data = True):
            a = [0]*2
            a[0] = data['y']
            a[1] = data['x']
            nodes[c] = a
        edges = {}

        for c in G.nodes(data = False):
            d = G.edges(c)
            if len(d) == 0:
                edges[c] = None
            for u, v in G.edges(c):
                if edges.get(u, None) == None:
                    edges[u] = {}
                    edges[u][v] = G.get_edge_data(c, v)[0]['val']
                else:
                    edges[u][v] = G.get_edge_data(c, v)[0]['val']
        Gform[0] = nodes
        Gform[1] = edges
        self.save_obj(Gform, fr'E:\YandexDisk\Другие материалы\Диплом\Производственная практика\program\{filename}.pickle')


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