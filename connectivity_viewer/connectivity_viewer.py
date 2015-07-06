# -*- coding: utf-8 -*-
__author__ = 'tieni'

from copy import deepcopy
import cProfile
import matplotlib
matplotlib.use('module://backend_qt5agg')
from backend.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from backend.signal import Signal
from matplotlib import cm, colors
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable


from networkx import read_graphml
import numpy as np
from orderedset import OrderedSet

from PythonQt.QtCore import QDir
from PythonQt.QtGui import QAbstractItemView, QFileDialog, QGridLayout, QHeaderView, QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,\
                            QLabel, QMainWindow, QMenu, QSizePolicy, QWidget, QVBoxLayout
from PythonQt import Qt
from zipfile import ZipFile

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
        <key id="d0" for="edge" attr.name="size" attr.type="double"/>
        <key id="d1" for="edge" attr.name="type" attr.type="string"/>
        <graph id="neurons" edgedefault="directed">
            <node id="neuron id 1"/>
            <node id="neuron id 2"/>
            <edge id="synapse id 1" source="neuron id 1" target="neuron id 2">
                <data key="d0">5</data>
                <data key="d1">e.g. inhibitory, excitatory etc.</data>
            </edge>
        </graph>
    </graphml>
"""

class Synapse(object):
    synapses = {}  # {(source, target): [synapse, ...], ...}
    source_neurons = OrderedSet()  # convenience access to all source neurons
    target_neurons = OrderedSet()  # convenience access to all target neurons

    @classmethod
    def reset(cls):
        cls.source_neurons.clear()
        cls.target_neurons.clear()
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

class NeuronView(object):
    """
    Data structure for synchronization between neuron data and their view
    """
    def __init__(self, name, context_menu, table_parent=None):
        self.data = OrderedSet()
        self.items = OrderedSet()
        self.table = QTableWidget(table_parent)
        self.table.setColumnCount(1)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalHeaderLabels((name, ))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(context_menu)

    def update_table(self):
        self.table.clearContents()
        self.table.setRowCount(len(self.data))
        for row, item in enumerate(self.items):
            self.table.setItem(row, 0, item)

    def add(self, data):
        self.data |= data
        self.items = OrderedSet([QTableWidgetItem(element) for element in self.data])
        self.update_table()

    def clear(self):
        self.data.clear()
        self.items.clear()
        self.update_table()

    def remove_selected(self):
        for index in sorted(self.table.selectedIndexes(), reverse=True):
            item = self.table.itemFromIndex(index)
            self.data.remove(item.text())
            self.items.remove(item)
            self.table.removeRow(index.row())


class MatrixEditor(QWidget):
    """
    With the matrix editor the user can define if neurons should be shown in their pre-synaptic or post-synaptic role
    or if they should be hidden.
    """
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Matrix Editor")
        self.total_view = NeuronView("All neurons", self.all_context_menu)
        self.source_view = NeuronView("Pre-synaptic neurons", self.src_context_menu)
        self.target_view = NeuronView("Post-synaptic neurons", self.target_context_menu)

        self.clear_source_button = QPushButton("Clear")
        self.clear_target_button = QPushButton("Clear")
        self.reset_button = QPushButton("Reset matrix")
        self.apply_button = QPushButton("Apply")  # clicked event connected by parent window

        layout = QGridLayout()
        layout.addWidget(self.total_view.table, 0, 0, rowSpan=1, columnSpan=-1)
        layout.addWidget(self.source_view.table, 1, 0)
        layout.addWidget(self.target_view.table, 1, 1)
        layout.addWidget(self.clear_source_button, 2, 0)
        layout.addWidget(self.clear_target_button, 2, 1)
        layout.addWidget(self.reset_button, 3, 0)
        layout.addWidget(self.apply_button, 3, 1)
        self.setLayout(layout)
        self.clear_source_button.clicked.connect(self.source_view.clear)
        self.clear_target_button.clicked.connect(self.target_view.clear)
        self.reset_button.clicked.connect(self.default_view)

    def src_context_menu(self, pos):
        context_menu = QMenu()
        context_menu.addAction("Remove from view", self.source_view.remove_selected)
        context_menu.exec_(self.source_view.table.viewport().mapToGlobal(pos))

    def target_context_menu(self, pos):
        context_menu = QMenu()
        context_menu.addAction("Remove from view", self.target_view.remove_selected)
        context_menu.exec_(self.target_view.table.viewport().mapToGlobal(pos))

    def all_context_menu(self, pos):
        context_menu = QMenu()
        context_menu.addAction("View in pre-synaptic role", self.move_to_sources)
        context_menu.addAction("View in post-synaptic role", self.move_to_targets)
        context_menu.exec_(self.total_view.table.viewport().mapToGlobal(pos))

    def get_source(self, index):
        return self.source_view.data[index]

    def get_target(self, index):
        return self.target_view.data[index]

    def move_to_sources(self):
        new_source_neurons = {item.text() for item in self.total_view.table.selectedItems()}
        self.source_view.add(new_source_neurons)

    def move_to_targets(self):
        new_target_neurons = {item.text() for item in self.total_view.table.selectedItems()}
        self.target_view.add(new_target_neurons)

    def default_view(self):
        self.total_view.clear()
        self.source_view.clear()
        self.target_view.clear()
        self.total_view.add(Synapse.source_neurons | Synapse.target_neurons)
        self.source_view.add(Synapse.source_neurons)
        self.target_view.add(Synapse.target_neurons)

class MatplotlibCanvas(FigureCanvas):
    """
    The MatplotlibCanvas contains the visualized connectivity matrix
    """
    hovered = Signal()
    clicked = Signal()

    def __init__(self, parent=None):
        self.sources = OrderedSet()
        self.targets = OrderedSet()
        self.figure = Figure()
        self.figure.set_tight_layout(True)
        self.matrix_axes = self.figure.add_subplot(111)
        divider = make_axes_locatable(self.matrix_axes)
        self.color_axes = divider.append_axes("right", size=0.1, pad=0.05)
        self.matrix_axes.hold(False)
        self.color_axes.hold(False)
        self.matrix_axes.set_xticks([])
        self.matrix_axes.set_yticks([])
        self.color_axes.set_xticks([])
        self.color_axes.set_yticks([])
        FigureCanvas.__init__(self, self.figure)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.synapse_matrix = np.array([], dtype=np.uint32)
        self.hovered_cell = None

    def build_connectivity_matrix(self, source_neurons, target_neurons):
        self.sources = source_neurons
        self.targets = target_neurons
        # fill data matrix
        self.synapse_matrix = np.zeros((len(source_neurons), len(target_neurons)), dtype=np.uint32)
        for neurons, synapse_list in Synapse.synapses.items():
            try:
                row = source_neurons.index(neurons[0])
                col = target_neurons.index(neurons[1])
                self.synapse_matrix[row, col] = len(synapse_list)
            except ValueError:
                continue

        # plot the data
        palette = cm.get_cmap("jet")
        mapped_colors = palette(np.linspace(0, 1, 1 + np.max(self.synapse_matrix) - np.min(self.synapse_matrix)))
        color_map = colors.ListedColormap(mapped_colors)
        # plot synapse matrix
        color_mesh = self.matrix_axes.pcolormesh(self.synapse_matrix, cmap=color_map, edgecolors='grey')
        self.matrix_axes.set_xlim(xmax=self.synapse_matrix.shape[1])  # needed to fit mesh into axes
        self.matrix_axes.set_ylim(ymax=self.synapse_matrix.shape[0])
        # hide tick lines
        self.matrix_axes.set_xticks([])
        self.matrix_axes.set_yticks([])
        # place ticks at middle of each row / column
        self.matrix_axes.set_xticks(np.arange(len(target_neurons)) + 0.5)
        self.matrix_axes.set_yticks(np.arange(len(source_neurons)) + 0.5)
        # add tick labels
        self.matrix_axes.set_yticklabels(source_neurons)
        self.matrix_axes.set_xticklabels(target_neurons, rotation='vertical')
        # plot color bar
        bounds = np.arange(len(np.unique(self.synapse_matrix)) + 1)
        colorbar = self.figure.colorbar(color_mesh, cax=self.color_axes, orientation='vertical')
        colorbar.set_ticks(bounds[:-1])
        bar_ticks = np.arange(np.min(self.synapse_matrix), 1 + np.max(self.synapse_matrix))
        colorbar.set_ticklabels(bar_ticks)

        def cell_clicked(event):
            if event.inaxes == self.matrix_axes:
                self.clicked.emit(int(event.ydata), int(event.xdata))

        def mouse_moved(event):
            if event.inaxes == self.matrix_axes:
                index = (int(event.xdata), int(event.ydata))
                if self.hovered_cell == index:
                    return
                self.hovered_cell = index
                self.hovered.emit(index[1], index[0])

        self.figure.canvas.mpl_connect('motion_notify_event', mouse_moved)
        self.figure.canvas.mpl_connect('button_press_event', cell_clicked)
        self.draw()

    def reset(self):
        self.synapse_matrix = np.array([])



class ConnectivityViewer(QMainWindow):
    """
    This is the plugin's main window, containing a menubar for loading a synapse file and holding the MatplotlibCanvas
    """

    synapse_file_loaded = Signal()

    def __init__(self, parent=knossos_global_mainwindow):
        super(ConnectivityViewer, self).__init__(parent)
        self.setWindowFlags(Qt.Qt.Window)
        self.setAttribute(Qt.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Connectivity Viewer")
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)

        self.synapse_viewer = SynapseViewer()
        self.matrix_editor = MatrixEditor()
        self.annotation_files = []

        self.file_menu = QMenu("File")
        self.file_menu.addAction("Load Synapse file", self.file_dialog_request)

        def show_matrix_editor(): self.matrix_editor.show()
        self.file_menu.addAction("Edit Matrix", show_matrix_editor)

        def quit_plugin(): self.close()
        self.file_menu.addAction("Quit", quit_plugin)
        self.menuBar().addMenu(self.file_menu)

        self.synapse_label = QLabel("")
        self.main_widget = QWidget(self)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.matrix_canvas = MatplotlibCanvas(self.main_widget)

        layout = QVBoxLayout(self.main_widget)
        layout.addWidget(self.synapse_label)
        layout.addWidget(self.matrix_canvas)

        self.matrix_canvas.hovered.connect(self.draw_synapse_label)
        self.matrix_canvas.clicked.connect(self.synapse_viewer_called)

        self.synapse_file_loaded.connect(self.plot_default_matrix)
        self.matrix_editor.apply_button.clicked.connect(self.apply_new_view)

    def file_dialog_request(self):
        # path = QFileDialog.getOpenFileName(None, "Select a connectivity file", QDir.homePath(), "Synapse file (*.graphml, *.k.zip)")
        # if len(path) > 0:
        #     self.load_synapse_file(path)
        self.load_synapse_file("/home/tieni/Desktop/wiring.graphml")

    def load_synapse_file(self, path):
        def do():
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

            Synapse.source_neurons = OrderedSet(neuron for neuron, degree in graph.out_degree().items() if degree > 0)
            Synapse.target_neurons = OrderedSet(neuron for neuron, degree in graph.in_degree().items() if degree > 0)
            for node in graph.nodes():
                for target, synapses in graph[node].items():
                    Synapse.synapses[(node, target)] = []
                    for syn in synapses.values():
                        syn_size = 0
                        syn_type = ""
                        try:
                            syn_size = syn["size"]
                        except KeyError:
                            pass
                        try:
                            syn_type = syn["type"]
                        except KeyError:
                            pass
                        Synapse.synapses[(node, target)].append(Synapse(node, target, syn["id"], syn_size, syn_type))
            self.synapse_file_loaded.emit()
        cProfile.runctx("do()", globals(), locals())

    def draw_synapse_label(self, src_index, target_index):
        num_synapses = self.matrix_canvas.synapse_matrix[src_index, target_index]
        source = self.matrix_canvas.sources[src_index]
        target = self.matrix_canvas.targets[target_index]
        self.synapse_label.setText('"{0}" → "{1}": {2} Synapses'.format(source, target, num_synapses))

    def apply_new_view(self):
        editor = self.matrix_editor
        self.matrix_canvas.build_connectivity_matrix(deepcopy(editor.source_view.data), deepcopy(editor.target_view.data))
        editor.close()

    def plot_default_matrix(self):
        self.matrix_editor.default_view()
        self.apply_new_view()

    def synapse_viewer_called(self, source_index, target_index):
        try:
            source = self.matrix_canvas.sources[source_index]
            target = self.matrix_canvas.targets[target_index]
            self.synapse_viewer.update(source, target, Synapse.synapses[(source, target)])
            self.synapse_viewer.show()
        except KeyError:
            return

    def reset(self):
        self.annotation_files = []
        self.matrix_canvas.reset()
        Synapse.reset()

    def closeEvent(self):
        self.matrix_editor.close()
