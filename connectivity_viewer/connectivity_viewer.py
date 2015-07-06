# -*- coding: utf-8 -*-
__author__ = 'tieni'

import matplotlib
matplotlib.use('module://backend_qt5agg')
from matplotlib import cm, colors, pyplot as plt
from .backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec

from networkx import read_graphml

from PythonQt.QtCore import QObject, SIGNAL, SLOT
from PythonQt.QtGui import QAbstractItemView, QFileDialog, QGridLayout, QHeaderView, QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,\
                            QLabel, QMainWindow, QMenu, QSizePolicy, QWidget, QVBoxLayout
from PythonQt import Qt

# from PyQt5.QtCore import pyqtSignal
# from PyQt5.QtWidgets import QLabel as PyQLabel, QMainWindow as PyQMainWindow, QMenu as PyQMenu, QSizePolicy as PyQSizePolicy, QWidget as PyQWidget, QVBoxLayout as PyQVBoxLayout
# from PyQt5.Qt import Qt as PyQt

from zipfile import ZipFile

import numpy as np

# KNOSSOS_PLUGIN Name ConnectivityViewer
# KNOSSOS_PLUGIN Version 1
# KNOSSOS_PLUGIN Description Reads in a .graphml synapse file and displays a connectivity matrix for it

"""
    This plugin shows a connectivity matrix based on a synapse file.
    It lists all synapses between every pair of neurons and allows jumping to their respective active zones.

    The synapse file is of type .graphml. To associate it with an annotation, the .graphml can be stored in a .k.zip
    along with the annotation. On loading the .k.zip, both the synapse information and the annotation are loaded.

    The associated annotation should have following format:
    One synapse denotes a tree with at least one node. The tree's comment must contain a unique synapse id.
    The node should be positioned at the synapse's active zone and bear the comment "az".
    This is where KNOSSOS jumps to when selecting the synapse.

    A minimal example for the .graphml synapse format:

    <?xml version="1.0" encoding="UTF-8"?>
    <graphml xmlns="http://graphml.graphdrawing.org/xmlns"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
        <key id="size" for="edge" attr.name="size" attr.type="double"/>
        <key id="type" for="edge" attr.name="type" attr.type="string"/>
        <graph id="neurons" edgedefault="directed">
            <node id="neuron id 1"/>
            <node id="neuron id 2"/>
            <edge id="synapse id 1" source="neuron id 1" target="neuron id 2">
                <data key="size">5</data>
                <data key="type">e.g. inhibitory, excitatory etc.</data>
            </edge>
        </graph>
    </graphml>
"""

class Synapse(object):
    synapses = {}  # {(source, target): [synapse, ...], ...}
    source_neurons = []
    target_neurons = []

    @classmethod
    def reset(cls):
        cls.source_neurons = []
        cls.target_neurons = []
        cls.synapses = {}

    def __init__(self, source, target, name, size, synapse_type):
        """
        :param source: source neuron id
        :param target: target neuron id
        :param name: synapse name
        :param size: synapse size
        :param synapse_type: e.g. "inhibitory", "excitatory" etc.
        """
        self.source = source
        self.target = target
        self.name = name
        self.size = size
        self.type = synapse_type

class SynapseViewer(QWidget):
    """
    This widget lists all synapses between selected source and target neurons. Jump to the synapse by clicking on it.
    """
    def __init__(self, parent=knossos_global_mainwindow):
        super(SynapseViewer, self).__init__(parent)
        self.setWindowFlags(Qt.Qt.Window)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(("Name", "type", "size"))
        self.table.setColumnCount(3)
        self.table.itemClicked.connect(self.jump_to_synapse)
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)

    def update(self, source, target, data):
        self.setWindowTitle("{0} → {1}".format(source, target))
        self.table.clear()
        items = [QTreeWidgetItem(self.table, (synapse.name, synapse.type, synapse.size)) for synapse in data]
        self.table.addTopLevelItems(items)

    def jump_to_synapse(self, item, column):
        trees = skeleton.find_trees(item.text(0))
        if len(trees) > 0:
            nodes = skeleton.find_nodes_in_tree(trees[0], "az")
            if len(nodes) > 0:
                skeleton.jump_to_node(nodes[0])

class MatrixEditor(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Matrix Editor")

        self.unused_neurons = []
        self.source_neurons = []
        self.target_neurons = []

        self.neuron_table = QTableWidget()
        self.source_table = QTableWidget()
        self.target_table = QTableWidget()

        def init_table(table, name):
            table.setColumnCount(1)
            table.verticalHeader().setVisible(False)
            table.setHorizontalHeaderLabels((name,))
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch);
            table.setDragDropMode(QAbstractItemView.DragDrop)
        init_table(self.neuron_table, "Unused neurons")
        init_table(self.source_table, "Source neurons")
        init_table(self.target_table, "Target neurons")

        self.clear_source_button = QPushButton("Clear")
        self.clear_target_button = QPushButton("Clear")
        self.reset_button = QPushButton("Reset matrix")
        self.apply_button = QPushButton("Apply")

        layout = QGridLayout()
        layout.addWidget(self.neuron_table, 0, 0, rowSpan=1, columnSpan=-1)
        layout.addWidget(self.source_table, 1, 0)
        layout.addWidget(self.target_table, 1, 1)
        layout.addWidget(self.clear_source_button, 2, 0)
        layout.addWidget(self.clear_target_button, 2, 1)
        layout.addWidget(self.reset_button, 3, 0)
        layout.addWidget(self.apply_button, 3, 1)
        self.setLayout(layout)

        def clear_sources():
            self.source_table.clearContents()
            self.unused_neurons.append(self.source_neurons)
            self.source_neurons = []

        def clear_targets():
            self.target_table.clearContents()
            self.unused_neurons.append(self.target_neurons)
            self.target_neurons = []

        self.clear_source_button.clicked.connect(clear_sources)
        self.clear_target_button.clicked.connect(clear_targets)
        self.reset_button.clicked.connect(self.default_view)

    def default_view(self):
        self.source_table.clearContents()
        self.target_table.clearContents()
        self.source_neurons = Synapse.source_neurons
        self.target_neurons = Synapse.target_neurons
        self.source_table.setRowCount(len(self.source_neurons))
        self.target_table.setRowCount(len(self.target_neurons))
        for i, neuron in enumerate(self.source_neurons):
            self.source_table.setItem(i, 0, QTableWidgetItem(neuron))
        for i, neuron in enumerate(self.target_neurons):
            self.target_table.setItem(i, 0, QTableWidgetItem(neuron))
        # source_items = [QTableWidgetItem(neuron) for neuron in self.source_neurons]
        # target_items = [QTableWidgetItem(neuron) for neuron in self.target_neurons]
        # self.source_table.addTopLevelItems(source_items)
        # self.target_table.addTopLevelItems(target_items)

class MatplotlibCanvas(FigureCanvas):
    """
    The MatplotlibCanvas contains the visualized connectivity matrix
    """
    # hovered = pyqtSignal(int, int)
    # clicked = pyqtSignal(tuple)

    def __init__(self, parent=None):
        self.figure = Figure()
        gridspec = GridSpec(1, 15)
        matrix_axes_spec = gridspec.new_subplotspec((0, 0), colspan=13)
        color_axes_spec = gridspec.new_subplotspec((0, 14), colspan=1)
        self.matrix_axes = self.figure.add_subplot(matrix_axes_spec)
        self.color_axes = self.figure.add_subplot(color_axes_spec)

        FigureCanvas.__init__(self, self.figure)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.synapse_matrix = np.array([], dtype=np.uint32)
        self.hovered_cell = None

    def build_connectivity_matrix(self, source_neurons, target_neurons):
        # fill data matrix
        self.synapse_matrix = np.zeros((len(source_neurons), len(target_neurons)), dtype=np.uint32)
        for neurons, synapse_list in Synapse.synapses.items():
            row = source_neurons.index(neurons[0])
            col = target_neurons.index(neurons[1])
            self.synapse_matrix[row, col] = len(synapse_list)

        # plot the data
        palette = cm.get_cmap("RdBu")
        mapped_colors = palette(np.linspace(0, 1, 1 + np.max(self.synapse_matrix) - np.min(self.synapse_matrix)))
        color_map = colors.ListedColormap(mapped_colors)
        # plot synapse matrix
        color_mesh = self.matrix_axes.pcolormesh(self.synapse_matrix, cmap=color_map)
        # hide tick lines
        for tic in self.matrix_axes.xaxis.get_major_ticks():
            tic.tick1On = tic.tick2On = False
        for tic in self.matrix_axes.yaxis.get_major_ticks():
            tic.tick1On = tic.tick2On = False
        # place ticks at middle of each row / column
        self.matrix_axes.set_xticks(np.arange(len(target_neurons)) + 0.5)
        self.matrix_axes.set_yticks(np.arange(len(source_neurons)) + 0.5)
        # add tick labels
        self.matrix_axes.set_yticklabels(source_neurons)
        self.matrix_axes.set_xticklabels(target_neurons)
        self.figure.autofmt_xdate()  # rotate x axis labels to fit more
        # plot color bar
        bounds = np.arange(len(np.unique(self.synapse_matrix)) + 1)
        colorbar = plt.colorbar(color_mesh, boundaries=bounds, values=bounds[:-1], cax=self.color_axes, orientation='vertical')
        colorbar.set_ticks(bounds[:-1] + .5)
        bar_ticks = np.arange(np.min(self.synapse_matrix), 1 + np.max(self.synapse_matrix))
        colorbar.set_ticklabels(bar_ticks)

        def cell_clicked(event):
            if event.inaxes == self.matrix_axes:
                pos = int(event.xdata), int(event.ydata)
                neuron_pair = (source_neurons[pos[1]], target_neurons[pos[0]])
                self.emit(SIGNAL("clicked"), neuron_pair)

        def mouse_moved(event):
            if event.inaxes == self.matrix_axes:
                index = (int(event.xdata), int(event.ydata))
                if self.hovered_cell == index:
                    return
                self.hovered_cell = index
                self.emit(SIGNAL("hovered"), index[1], index[0])

        self.figure.canvas.mpl_connect('motion_notify_event', mouse_moved)
        self.figure.canvas.mpl_connect('button_press_event', cell_clicked)
        self.draw()

    def reset(self):
        self.synapse_matrix = np.array([])



class ConnectivityViewer(QMainWindow):
    """
    This is the plugin's main window, containing a menubar for loading a synapse file and holding the MatplotlibCanvas
    """
    # synapse_file_loaded = pyqtSignal()

    def __init__(self, parent=knossos_global_mainwindow):
        super(ConnectivityViewer, self).__init__(parent)
        self.setWindowFlags(Qt.Qt.Window)
        self.setAttribute(Qt.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Connectivity Viewer")

        self.synapse_viewer = SynapseViewer()
        self.matrix_editor = MatrixEditor()
        self.annotation_files = []

        self.file_menu = QMenu("File")
        self.file_menu.addAction("Load Synapse file", self.file_dialog_request)
        self.file_menu.addAction("Edit Matrix", self.matrix_editor.show)
        self.file_menu.addAction("Quit", self.close)
        self.menuBar().addMenu(self.file_menu)

        self.synapse_label = QLabel("")
        self.main_widget = QWidget(self)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.matrix_canvas = MatplotlibCanvas(self.main_widget)

        layout = QVBoxLayout(self.main_widget)
        layout.addWidget(self.synapse_label)
        layout.addWidget(self.matrix_canvas)

        QObject.connect(self.matrix_canvas, SIGNAL("hovered"), self, SLOT("draw_synapse_label"))
        QObject.connect(self.matrix_canvas, SIGNAL("clicked"), self, SLOT("synapse_viewer_called"))

        QObject.connect(self, SIGNAL("synapse_file_loaded"), self, SLOT("plot_default_matrix"))
        self.matrix_editor.apply_button.clicked.connect(self.apply_new_view)

        # def quit_viewer(eocd, close_event):
        #     self.close()
        # signalRelay.Signal_MainWindow_closeEvent.connect(quit_viewer)

    def file_dialog_request(self):
        # path = QFileDialog.getOpenFileName(None, "Select a connectivity file", QDir.homePath(), "Synapse file (*.graphml, *.k.zip)")
        # if len(path) > 0:
        #     self.load_synapse_file(path)
        self.load_synapse_file("/home/tieni/Desktop/synapses.graphml")

    def load_synapse_file(self, path):
        """
        Reads in a .graphml synapse file and displays a connectivity matrix
        """
        self.reset()
        graph = None
        if path.endswith(".k.zip"):
            with ZipFile(path, 'r') as annotation_file:
                for name in annotation_file.namelist():
                    if name.endswith(".graphml"):
                        graph = read_graphml(annotation_file.open(name))
                if graph is None:
                    print("No synapse file found in", path)
                    return
                skeleton.annotation_load(path, False)

        else:  # ends with .graphml
            graph = read_graphml(path)

        Synapse.source_neurons = [neuron for neuron, degree in graph.out_degree().items() if degree > 0]
        Synapse.target_neurons = [neuron for neuron, degree in graph.in_degree().items() if degree > 0]
        for node in graph.nodes():
            for target, synapses in graph[node].items():
                Synapse.synapses[(node, target)] = \
                    [Synapse(node, target, syn["id"], syn["size"], syn["type"]) for syn in synapses.values()]

        self.emit(SIGNAL("synapse_file_loaded"))

    def draw_synapse_label(self, src_index, target_index):
        num_synapses = self.matrix_canvas.synapse_matrix[src_index, target_index]
        self.synapse_label.setText('"{0}" → "{1}": {2} Synapses'.format(Synapse.source_neurons[src_index], Synapse.target_neurons[target_index], num_synapses))

    def apply_new_view(self):
        editor = self.matrix_editor
        self.matrix_canvas.build_connectivity_matrix(editor.source_neurons, editor.target_neurons)
        editor.close()

    def plot_default_matrix(self):
        self.matrix_editor.default_view()
        self.apply_new_view()

    def synapse_viewer_called(self, neuron_pair):
        try:
            self.synapse_viewer.update(neuron_pair[0], neuron_pair[1], Synapse.synapses[neuron_pair])
            self.synapse_viewer.show()
        except KeyError:
            return

    def reset(self):
        self.annotation_files = []
        self.matrix_canvas.reset()
        Synapse.reset()
