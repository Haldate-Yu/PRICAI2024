# -*- coding: utf-8 -*-
import argparse
import os
import sys
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import collections as mc
import matplotlib.pyplot as plt

from epynet import Network

sys.path.insert(0, os.path.join('..'))
from utils.graph_utils import get_nx_graph, get_sensitivity_matrix
from utils.SensorInstaller import SensorInstaller
from utils.DataReader import DataReader

# ----- ----- ----- ----- ----- -----
# Command line arguments
# ----- ----- ----- ----- ----- -----
parser = argparse.ArgumentParser()
parser.add_argument(
    '--wds',
    default='anytown',
    type=str
)
parser.add_argument(
    '--nodesize',
    default=7,
    type=int,
    help="Size of nodes on the plot."
)
parser.add_argument(
    '--perturb',
    default=None,
    type=int
)
args = parser.parse_args()

pathToRoot = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
pathToModels = os.path.join(pathToRoot, 'experiments', 'models')
pathToDB = os.path.join(pathToRoot, 'data', 'db_' + args.wds + '_doe_pumpfed_1')

wds = Network(os.path.join('..', 'water_networks', args.wds + '.inp'))
wds.solve()

print('Calculating nodal sensitivity to demand change...\n')
ptb = np.max(wds.junctions.basedemand) / 100
if args.perturb:
    G = get_nx_graph(wds)
    reader = DataReader(
        pathToDB,
        n_junc=len(wds.junctions),
        node_order=np.array(list(G.nodes)) - 1
    )
    demands, _, _ = reader.read_data(
        dataset='trn',
        varname='junc_demands',
        rescale=None,
        cover=False
    )
    demands = pd.Series(demands[args.perturb, :, 0], index=wds.junctions.uid)
    wds.junctions.basedemand = demands

S = get_sensitivity_matrix(wds, ptb)


def get_node_df(elements, get_head=False):
    data = []
    for junc in elements:
        ser = pd.Series({
            'uid': junc.uid,
            'x': junc.coordinates[0],
            'y': junc.coordinates[1],
        })
        if get_head:
            ser['head'] = junc.head
        data.append(ser)
    data = pd.DataFrame(data)
    if get_head:
        data['head'] = (data['head'] - data['head'].min()) / (data['head'].max() - data['head'].min())
    return data


def get_elem_df(elements, nodes):
    data = []
    df = pd.DataFrame(data)
    if elements:
        for elem in elements:
            ser = pd.Series({
                'uid': elem.uid,
                'x1': nodes.loc[nodes['uid'] == elem.from_node.uid, 'x'].values,
                'y1': nodes.loc[nodes['uid'] == elem.from_node.uid, 'y'].values,
                'x2': nodes.loc[nodes['uid'] == elem.to_node.uid, 'x'].values,
                'y2': nodes.loc[nodes['uid'] == elem.to_node.uid, 'y'].values,
            })
            data.append(ser)
        df = pd.DataFrame(data)
        df['x1'] = df['x1'].str[0]
        df['y1'] = df['y1'].str[0]
        df['x2'] = df['x2'].str[0]
        df['y2'] = df['y2'].str[0]
        df['center_x'] = (df['x1'] + df['x2']) / 2
        df['center_y'] = (df['y1'] + df['y2']) / 2
        df['orient'] = np.degrees(np.arctan((df['y2'] - df['y1']) / (df['x2'] - df['x1']))) + 90
    return df


def build_lc_from(df):
    line_collection = []
    for elem_id in df['uid']:
        line_collection.append([
            (df.loc[df['uid'] == elem_id, 'x1'].values[0],
             df.loc[df['uid'] == elem_id, 'y1'].values[0]),
            (df.loc[df['uid'] == elem_id, 'x2'].values[0],
             df.loc[df['uid'] == elem_id, 'y2'].values[0])
        ])
    return line_collection


nodes = get_node_df(wds.nodes, get_head=True)
juncs = get_node_df(wds.junctions, get_head=True)
tanks = get_node_df(wds.tanks)
reservoirs = get_node_df(wds.reservoirs)
pipes = get_elem_df(wds.pipes, nodes)
pumps = get_elem_df(wds.pumps, nodes)
valves = get_elem_df(wds.valves, nodes)
pipe_collection = build_lc_from(pipes)
pump_collection = build_lc_from(pumps)
if not valves.empty:
    valve_collection = build_lc_from(valves)

mew = .5
fig, ax = plt.subplots()
lc = mc.LineCollection(pipe_collection, linewidths=mew, color='k')
ax.add_collection(lc)
lc = mc.LineCollection(pump_collection, linewidths=mew, color='k')
ax.add_collection(lc)
if not valves.empty:
    lc = mc.LineCollection(valve_collection, linewidths=mew, color='k')
    ax.add_collection(lc)

nodal_s = np.sum(np.abs(S), axis=0)
nodal_s = (nodal_s - nodal_s.min()) / nodal_s.max()
colors = []
cmap = plt.get_cmap('plasma')
for idx, junc in juncs.iterrows():
    color = cmap(nodal_s[idx])
    colors.append(color)
    ax.plot(junc['x'], junc['y'], 'ko', mfc=color, mec='k', ms=args.nodesize, mew=mew)

for _, tank in tanks.iterrows():
    ax.plot(tank['x'], tank['y'], marker=7, mfc='k', mec='k', ms=7, mew=mew)
for _, reservoir in reservoirs.iterrows():
    ax.plot(reservoir['x'], reservoir['y'], marker='o', mfc='k', mec='k', ms=3, mew=mew)
ax.plot(pumps['center_x'], pumps['center_y'], 'ko', ms=7, mfc='white', mew=mew)
for _, pump in pumps.iterrows():
    ax.plot(pump['center_x'], pump['center_y'],
            marker=(3, 0, pump['orient']),
            color='k',
            ms=5
            )
ax.autoscale()
ax.axis('off')
plt.tight_layout()
plt.show()
