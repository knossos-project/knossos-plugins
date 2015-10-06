from PythonQt import QtGui, Qt
import KnossosModule
from math import sqrt
import networkx as nx
import time
import sys

# little shortcut for fast dev
connectome_analysis_toolbox_path = 'C:/repos/CAT/'
sys.path.append(connectome_analysis_toolbox_path)

from cat.connection import Connection


from cat import morphology
skeleton = morphology.get_skeleton(c, SKELETON_ID )

from cat import labeling, features
labeling.update_skeleton_edge_with_distance( skeleton )
print features.get_total_cable_length( skeleton )

#KNOSSOS_PLUGIN Name CatmaidConnector
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Connect and interact with a Django-based catmaid backend to retrieve and upload skeletons

class CatConnect(QtGui.QWidget):
    def initGUI(self):
        self.twiHeadersList = []
        self.twiHash = {}
        # General
        self.setWindowTitle("Catmaid Connector")
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        nameLayout = QtGui.QHBoxLayout()
        layout.addLayout(nameLayout)
        nameLayout.addWidget(QtGui.QLabel("Enter instance URL: "))
        self.nameEdit = QtGui.QLineEdit()
        nameLayout.addWidget(self.nameEdit)
        buttonLayout = QtGui.QHBoxLayout()
        layout.addLayout(buttonLayout)

        #
        # selectPathButton = QtGui.QPushButton("Select Nodes")
        # selectPathButton.clicked.connect(self.selectPathButtonClicked)
        # buttonLayout.addWidget(selectPathButton)
        # self.clearButton = QtGui.QPushButton("Clear Table")
        # buttonLayout.addWidget(self.clearButton)
        # self.clearButton.clicked.connect(self.clearClicked)
        # self.logTable = QtGui.QTableWidget()
        # layout.addWidget(self.logTable)
        # self.setTableHeaders(self.logTable, ["Date/Time", "Name", "Node #1", "Node #2", "Length", "Hops", "Path"])
        # self.finalizeTable(self.logTable)
        # Show
        self.setWindowFlags(Qt.Qt.Window)
        self.show()
        return

    # def finalizeTable(self, table):
    #     table.horizontalHeader().setStretchLastSection(True)
    #     self.resizeTable(table)
    #     table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
    #     table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
    #     return
    #
    # def resizeTable(self, table):
    #     table.resizeColumnsToContents()
    #     table.resizeRowsToContents()
    #     return
    #
    # def clearTable(self, table):
    #     table.clearContents()
    #     del self.twiHash.setdefault(table,[])[:]
    #     table.setRowCount(0)
    #     return
    #
    #
    # def setTableHeaders(self, table, columnNames):
    #     columnNum = len(columnNames)
    #     table.setColumnCount(columnNum)
    #     for i in xrange(columnNum):
    #         twi = QtGui.QTableWidgetItem(columnNames[i])
    #         table.setHorizontalHeaderItem(i, twi)
    #         self.twiHeadersList.append(twi)
    #     return
    #
    # def addTableRow(self, table, columnTexts):
    #     rowIndex = 0
    #     table.insertRow(rowIndex)
    #     for i in xrange(len(columnTexts)):
    #         twi = QtGui.QTableWidgetItem(columnTexts[i])
    #         twi.setFlags(twi.flags() & (~Qt.Qt.ItemIsEditable))
    #         self.twiHash.setdefault(table,[]).append(twi)
    #         table.setItem(rowIndex, i, twi)
    #     self.resizeTable(table)
    #     return
    
    def __init__(self, parent=KnossosModule.knossos_global_mainwindow):
        super(CatConnect, self).__init__(parent, Qt.Qt.WA_DeleteOnClose)
        self.initGUI()
        self.paths = []
        return

    # def distance_scaled(self, source, target):
    #     c1 = source.coordinate()
    #     c2 = target.coordinate()
    #     x, y, z = c1.x() - c2.x(), c1.y() - c2.y(), c1.z() - c2.z()
    #     sx, sy, sz = KnossosModule.knossos.getScale()
    #     return sqrt(sum([(dim*dim) for dim in [x*sx, y*sy, z*sz]]))

    def getGraph(self):
        nxG = nx.Graph()
        for tree in KnossosModule.skeleton.trees():
            for node in tree.nodes():
                nxG.add_node(node)
                for segment in node.segments():
                    s, t = segment.source(), segment.target()
                    nxG.add_edge(s, t, weight=self.distance_scaled(s,t))
        return nxG

    def connect_instance(self):
        c = Connection( CATMAID_URL, USERNAME, PASSWORD, CATMAID_PROJECT_ID )
        c.login()

    # def clearClicked(self):
    #     self.clearTable(self.logTable)
    #     self.paths = []
    #     return
    #
    # def findPathButtonClicked(self):
    #     nxG = self.getGraph()
    #     sn = KnossosModule.skeleton.selectedNodes()
    #     if (len(sn) <> 2):
    #         QtGui.QMessageBox.information(0, "Error", "Select exactly two nodes")
    #         return
    #     n1, n2 = sn
    #     all_distance, all_path = nx.single_source_dijkstra(nxG, n1)
    #     if not (n2 in all_distance):
    #         QtGui.QMessageBox.information(0, "Error", "Nodes are not connected")
    #         return
    #     n1_str, n2_str = str(n1.node_id()), str(n2.node_id())
    #     distance_str = str(all_distance[n2])
    #     n2_path = all_path[n2]
    #     path_str = ",".join([str(n.node_id()) for n in n2_path])
    #     hops_str = str(len(n2_path)-1)
    #     datetime_str = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())
    #     name_str = self.nameEdit.text
    #     self.addTableRow(self.logTable, [datetime_str, name_str, n1_str, n2_str, distance_str, hops_str, path_str])
    #     self.paths.insert(0,n2_path)
    #     return
    #
    # def selectPathButtonClicked(self):
    #     si = self.logTable.selectedIndexes()
    #     if len(si) > 0:
    #         KnossosModule.skeleton.selectNodes(self.paths[si[0].row()])
    #     return

    pass

KnossosModule.plugin_container['CatConnect'] = CatConnect()
