from PythonQt import QtGui, Qt
import KnossosModule
from math import sqrt
import networkx as nx
import time
import sys

#KNOSSOS_PLUGIN Name CatmaidConnector
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Connect and interact with a Django-based catmaid backend to retrieve and upload skeletons

# little shortcut for fast dev
connectome_analysis_toolbox_path = 'C:/repos/CAT/'
sys.path.append(connectome_analysis_toolbox_path)

from cat.connection import Connection
from cat import morphology


class CatConnect(QtGui.QWidget):
    def initGUI(self):
        self.twiHeadersList = []
        self.twiHash = {}
        # General
        self.setWindowTitle("Catmaid Connector")
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        #nameLayout = QtGui.QHBoxLayout()
        #layout.addLayout(nameLayout)
        #nameLayout.addWidget(QtGui.QLabel("Enter instance URL: "))
        #self.nameEdit = QtGui.QLineEdit()
        #nameLayout.addWidget(self.nameEdit)
        buttonLayout = QtGui.QHBoxLayout()
        layout.addLayout(buttonLayout)

        connect_button = QtGui.QPushButton("Connect to catmaid")
        layout.addWidget(connect_button)
        connect_button.clicked.connect(self.connect_instance)

        get_skel_button = QtGui.QPushButton("Get skeleton")
        layout.addWidget(get_skel_button)
        get_skel_button.clicked.connect(self.get_skeleton_clicked)

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
        CATMAID_URL = 'http://localhost:9000'
        USERNAME = 'cat_root'
        PASSWORD = 'catcat'
        CATMAID_PROJECT_ID = 2
        self.active_connection = Connection( CATMAID_URL, USERNAME, PASSWORD, CATMAID_PROJECT_ID )
        QtGui.QMessageBox.information(0, "Success", "You are connected", QtGui.QMessageBox.Ok)
        self.active_connection.login()

    def get_skeleton(self, skel_id):
        skel_id = 41
        if self.active_connection:
            skeleton = self.active_connection.fetch('{0}/1/1/compact-skeleton'.format(41))
            #skeleton = morphology.get_skeleton(self.active_connection, skel_id )
        else:
            QtGui.QMessageBox.information(0, "Error", "Connect first", QtGui.QMessageBox.Ok)
        KnossosModule.skeleton.add_tree(1)
        # add nodes
        for n in skeleton[0]:
            KnossosModule.skeleton.add_node(int(n[0]), int(n[3]),int(n[4]),int(n[5]), 1)

        # add edges
        for e in skeleton[0]:
            if e[0] and e[1]:
                KnossosModule.skeleton.add_segment(int(e[0]), int(e[1]))


    def get_skeleton_clicked(self):
         self.get_skeleton(self)
         return
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
