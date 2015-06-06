from PythonQt import QtGui, Qt
import DatasetUtils, numpy, os, re, string, sys, traceback, Image, time
from scipy import ndimage
from skimage.morphology import watershed
DatasetUtils._set_noprint(True)
from matplotlib import pyplot as plt

#KNOSSOS_PLUGIN Name WatershedSplitter
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Iteratively split a volume into subobjects using a watershed algorithm on a pre-calculated prediction

class watershedSplitter(QtGui.QWidget):
    INSTRUCTION_TEXT_STR = """Fill configuration:
- Pick membrane prediction dataset by browsing to directory of knossos.conf
- Base subobject ID for subobjects to be created
- Beginning and size of work area as an x,y,z blank-separated tuples
- Margin size for actual algorithm (would not be eventually projected to knossos)
- Algorithmic parameters

Operation:
- Click begin to process configuration. This would confine movement to work area
- Iteratively:
-- Middle-click a coordinate inside a subobject to calculate watershed
-- Select masked subobject by clicking a row in SubObjects table,
   or click Undo to revert last coordinate placement
- Click either Finish to save changes into file or Reset to discard"""
    SUBOBJECT_TABLE_GROUP_STR = "Subobject Table"
    SUBOBJECT_ID_COLUMN_STR = "ID"
    SUBOBJECT_COORD_COLUMN_STR = "Coordinate"
    SUBOBJECT_MORE_COORDS_COLUMN_STR = "Subseeds Coordinates"
    OBJECT_LIST_COLUMNS = [SUBOBJECT_ID_COLUMN_STR, SUBOBJECT_COORD_COLUMN_STR, SUBOBJECT_MORE_COORDS_COLUMN_STR]

    class BusyCursorScope:
        def __init__(self):
            Qt.QApplication.setOverrideCursor(QtGui.QCursor(Qt.Qt.WaitCursor))
            Qt.QApplication.processEvents()
            return
        
        def __del__(self):
            Qt.QApplication.restoreOverrideCursor()
            Qt.QApplication.processEvents()
            return
        pass

    class MyTableWidget(QtGui.QTableWidget):
        def __init__(self, delF, sF, ctrlBF, parent=None):
            QtGui.QTableWidget.__init__(self,parent)
            self._delF = delF
            self._sF = sF
            self._ctrlBF = ctrlBF
            return

        def keyPressEvent(self, event):
            if event.key() == Qt.Qt.Key_Delete:
                self._delF()
            if event.key() == Qt.Qt.Key_Space:
                self._sF()
            if (event.key() == Qt.Qt.Key_B) and (event.modifiers() == Qt.Qt.ControlModifier):
                self._ctrlBF()
            return QtGui.QTableWidget.keyPressEvent(self,event)
        pass

    def initGUI(self):
        self.setWindowTitle("Watershed Splitter")
        self.widgetLayout = QtGui.QVBoxLayout()
        self.setLayout(self.widgetLayout)
        instructionsButton = QtGui.QPushButton("See Instructions")
        instructionsButton.clicked.connect(self.instructionsButtonClicked)
        self.widgetLayout.addWidget(instructionsButton)
        self.configGroupBox = QtGui.QGroupBox("Configuration")
        self.widgetLayout.addWidget(self.configGroupBox)
        configLayout = QtGui.QVBoxLayout()
        self.configGroupBox.setLayout(configLayout)
        self.widgetLayout.addLayout(configLayout)
        dirBrowseLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(dirBrowseLayout)
        dirBrowseLayout.addWidget(QtGui.QLabel("Membrane Prediction"))
        self.dirEdit = QtGui.QLineEdit()
        dirBrowseLayout.addWidget(self.dirEdit)
        self.dirBrowseButton = QtGui.QPushButton("Browse...")
        self.dirBrowseButton.clicked.connect(self.dirBrowseButtonClicked)
        dirBrowseLayout.addWidget(self.dirBrowseButton)
        subObjLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(subObjLayout)
        workAreaLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(workAreaLayout)
        workAreaLayout.addWidget(QtGui.QLabel("Coordinate"))
        self.workAreaBeginEdit = QtGui.QLineEdit()
        workAreaLayout.addWidget(self.workAreaBeginEdit)
        workAreaLayout.addWidget(QtGui.QLabel("Size"))
        self.workAreaSizeEdit = QtGui.QLineEdit()
        workAreaLayout.addWidget(self.workAreaSizeEdit)
        workAreaLayout.addWidget(QtGui.QLabel("Margin"))
        self.marginEdit = QtGui.QLineEdit()
        workAreaLayout.addWidget(self.marginEdit)
        params1Layout = QtGui.QHBoxLayout()
        configLayout.addLayout(params1Layout)
        params1Layout.addWidget(QtGui.QLabel("Marker Radius"))
        self.markerRadiusEdit = QtGui.QLineEdit()
        params1Layout.addWidget(self.markerRadiusEdit)
        params1Layout.addWidget(QtGui.QLabel("Base ID"))
        self.baseSubObjIdEdit = QtGui.QLineEdit()
        params1Layout.addWidget(self.baseSubObjIdEdit)
        params1Layout.addWidget(QtGui.QLabel("Membrane Threshold"))
        self.memThresEdit = QtGui.QLineEdit()
        params1Layout.addWidget(self.memThresEdit)
        slackLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(slackLayout)
        slackLayout.addWidget(QtGui.QLabel("Min Obj Size"))
        self.minObjSizeEdit = QtGui.QLineEdit()
        slackLayout.addWidget(self.minObjSizeEdit)
        slackLayout.addWidget(QtGui.QLabel("Auto Slack"))
        self.isSlackCheckBox = QtGui.QCheckBox()
        slackLayout.addWidget(self.isSlackCheckBox)
        slackLayout.addWidget(QtGui.QLabel("Erosions"))
        self.slackErosionItersEdit = QtGui.QLineEdit()
        slackLayout.addWidget(self.slackErosionItersEdit)
        self.isSlackCheckBox.stateChanged.connect(self.isSlackCheckBoxChanged)
        self.isSlackCheckBox.setChecked(False)
        self.isSlackCheckBoxChanged(False)
        opButtonsLayout = QtGui.QHBoxLayout()
        self.widgetLayout.addLayout(opButtonsLayout)
        self.beginButton = QtGui.QPushButton("Begin")
        self.beginButton.clicked.connect(self.beginButtonClicked)
        opButtonsLayout.addWidget(self.beginButton)
        self.undoButton = QtGui.QPushButton("Reset Subseeds")
        self.undoButton.enabled = False
        self.undoButton.clicked.connect(self.undoButtonClicked)
        opButtonsLayout.addWidget(self.undoButton)
        self.resetButton = QtGui.QPushButton("Reset")
        self.resetButton.enabled = False
        self.resetButton.clicked.connect(self.resetButtonClicked)
        opButtonsLayout.addWidget(self.resetButton)
        self.finishButton = QtGui.QPushButton("Finish")
        self.finishButton.enabled = False
        self.finishButton.clicked.connect(self.finishButtonClicked)
        opButtonsLayout.addWidget(self.finishButton)
        self.subObjTableGroupBox = QtGui.QGroupBox("SubObjects")
        subObjTableLayout = QtGui.QVBoxLayout()
        self.subObjTableGroupBox.setLayout(subObjTableLayout)
        tableSplit = QtGui.QSplitter()
        tableSplit.setOrientation(Qt.Qt.Horizontal)
        subObjTableLayout.addWidget(tableSplit)
        self.pendSubObjTable = self.MyTableWidget(self.pendSubObjTableDel, self.pendSubObjTableS, self.pendSubObjTableCtrlB)
        pendSubObjTableWidget = QtGui.QWidget()
        tableSplit.addWidget(pendSubObjTableWidget)
        pendSubObjTableLayout = QtGui.QVBoxLayout()
        pendSubObjTableWidget.setLayout(pendSubObjTableLayout)
        pendSubObjTableLayout.addWidget(QtGui.QLabel("Pending"))
        pendSubObjTableLayout.addWidget(self.pendSubObjTable)
        self.setTableHeaders(self.pendSubObjTable, self.OBJECT_LIST_COLUMNS)
        self.pendSubObjTable.cellClicked.connect(self.pendSubObjTableCellClicked)
        self.pendSubObjTable.itemSelectionChanged.connect(self.pendSubObjTableSelectionChanged)
        self.pendSubObjTable.cellDoubleClicked.connect(self.pendSubObjTableCellDoubleClicked)
        self.finalizeTable(self.pendSubObjTable)
        doneSubObjTableWidget = QtGui.QWidget()
        tableSplit.addWidget(doneSubObjTableWidget)
        doneSubObjTableLayout = QtGui.QVBoxLayout()
        doneSubObjTableWidget.setLayout(doneSubObjTableLayout)
        self.doneSubObjTable = self.MyTableWidget(self.doneSubObjTableDel, self.doneSubObjTableS, self.doneSubObjTableCtrlB)
        doneSubObjTableLayout.addWidget(QtGui.QLabel("Done"))
        doneSubObjTableLayout.addWidget(self.doneSubObjTable)
        self.setTableHeaders(self.doneSubObjTable, self.OBJECT_LIST_COLUMNS)
        self.doneSubObjTable.cellClicked.connect(self.doneSubObjTableCellClicked)
        self.doneSubObjTable.itemSelectionChanged.connect(self.doneSubObjTableSelectionChanged)
        self.doneSubObjTable.cellDoubleClicked.connect(self.doneSubObjTableCellDoubleClicked)
        self.finalizeTable(self.doneSubObjTable)
        # Invisibles
        self.workWidgetWidthEdit = QtGui.QLineEdit()
        self.workWidgetHeightEdit = QtGui.QLineEdit()
        self.confWidgetWidthEdit = QtGui.QLineEdit()
        self.confWidgetHeightEdit = QtGui.QLineEdit()
        self.curFont = QtGui.QFont()
        # Show
        self.setWindowFlags(Qt.Qt.Window)
        self.show()
        Qt.QApplication.processEvents()
        return

    def __init__(self, parent=knossos_global_mainwindow):
        super(watershedSplitter, self).__init__(parent, Qt.Qt.WA_DeleteOnClose)
        self.initGUI()
        self.initLogic()
        return

    def loadMembranePrediction(self, path, offset, size):
        # Load membrane prediction
        membraneDataset = DatasetUtils.knossosDataset()
        membraneDataset.initialize_from_knossos_path(path)
        memPred = membraneDataset.from_cubes_to_matrix(size, offset, type='raw')
        return numpy.invert(memPred > self.memThres)

    def finalizeTable(self, table):
        table.horizontalHeader().setStretchLastSection(True)
        self.resizeTable(table)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        return

    def applyGuiConfig(self):
        width = int(self.confWidgetWidthEdit.text)
        height = int(self.confWidgetHeightEdit.text)
        self.resize(width,height)
        return

    def generateGuiConfig(self):
        curWidth = self.size.width()
        curHeight = self.size.height()
        width = int(str(self.confWidgetWidthEdit.text))
        height = int(str(self.confWidgetHeightEdit.text))
        if (width <> curWidth) or (height <> curHeight):
            self.confWidgetWidthEdit.text = str(curWidth)
            self.confWidgetHeightEdit.text = str(curHeight)
        return

    def loadConfig(self):
        settings = Qt.QSettings()
        settings.beginGroup(self.pluginConf)
        for (widget,key,default) in self.settings:
            val = settings.value(key)
            if (val == None) or (str(val)==""):
                val_str = default
            else:
                val_str = str(val)
            if type(default)==type("a"):
                widget.text = val_str
            elif type(default)==type(True):
                widget.setChecked(bool(int(val_str)))
        settings.endGroup()
        return

    def saveConfig(self):
        settings = Qt.QSettings()
        settings.beginGroup(self.pluginConf)
        for (widget,key,default) in self.settings:
            if type(default)==type("a"):
                val_str = str(widget.text)
            elif type(default)==type(True):
                val_str = str(int(widget.isChecked()))
            settings.setValue(key,val_str)
        settings.endGroup()
        return

    def signalsConnect(self):
        for (signal, slot) in self.signalConns:
            signal.connect(slot)
        return
    
    def signalsDisonnect(self):
        for (signal, slot) in self.signalConns:
            signal.disconnect(slot)
        return

    def initLogic(self):
        self.active = False
        self.pluginConf = "Plugin_WatershedSplitter"
        self.settings = \
                      [(self.dirEdit,"DIR",""),
                        (self.baseSubObjIdEdit,"BASE_SUB_OBJ_ID","10000000"), \
                        (self.workAreaBeginEdit,"WORK_AREA_BEGIN",str(knossos.getPosition())), \
                        (self.workAreaSizeEdit,"WORK_AREA_SIZE",str(tuple([knossos.getCubeEdgeLength()]*3))), \
                        (self.marginEdit,"MARGIN","0"), \
                        (self.markerRadiusEdit,"MARKER_RADIUS","3"), \
                        (self.memThresEdit,"MEM_THRES","150"), \
                        (self.minObjSizeEdit,"MIN_OBJ_SIZE","500"), \
                       (self.isSlackCheckBox,"IS_SLACK",True), \
                       (self.slackErosionItersEdit,"SLACK_EROSION_ITERS","1"), \
                       (self.workWidgetWidthEdit,"WORK_WIDGET_WIDTH", "600"), \
                       (self.workWidgetHeightEdit,"WORK_WIDGET_HEIGHT", "400"), \
                       (self.confWidgetWidthEdit,"CONF_WIDGET_WIDTH", "0"), \
                       (self.confWidgetHeightEdit,"CONF_WIDGET_HEIGHT", "0")]
        self.loadConfig()
        self.applyGuiConfig()
        self.signalConns = []
        self.signalConns.append((signalRelay.Signal_EventModel_handleMouseReleaseMiddle, self.handleMouseReleaseMiddle))
        self.signalsConnect()
        return

    def uninitLogic(self):
        self.generateGuiConfig()
        self.saveConfig()
        plugin_container.remove(self)
        self.signalsDisonnect()
        return

    def closeEventYes(self,event):
        self.resetButtonClicked()
        self.uninitLogic()
        event.accept()
        return
    
    def closeEventNo(self,event):
        event.ignore()
        return
    
    def closeEvent(self,event):
        if not self.active:
            self.uninitLogic()
            event.accept()
            return
        mb = QtGui.QMessageBox()
        yes = QtGui.QMessageBox.Yes; no = QtGui.QMessageBox.No
        mb.setStandardButtons(yes | no)
        mb.setText("Closing while active!")
        mb.setInformativeText("This will reset, proceed?")
        mb.setStandardButtons(yes|no)
        action = {yes: self.closeEventYes, no: self.closeEventNo}
        action[mb.exec_()](event);
        return

    def setTableHeaders(self, table, columnNames):
        columnNum = len(columnNames)
        table.setColumnCount(columnNum)
        for i in xrange(columnNum):
            twi = QtGui.QTableWidgetItem(columnNames[i])
            table.setHorizontalHeaderItem(i, twi)
        return

    def clearTable(self, isDone):
        table = self.tableHash[isDone]["Table"]
        table.clearContents()
        table.setRowCount(0)
        return

    def resizeTable(self, table):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        return

    def addTableRow(self, table, columnTexts, isSlack, isTodo, atEnd = False):
        rowIndex = 0
        if atEnd:
            rowIndex = table.rowCount
        table.insertRow(rowIndex)
        for i in xrange(len(columnTexts)):
            twi = QtGui.QTableWidgetItem(columnTexts[i])
            twi.setFlags(twi.flags() & (~Qt.Qt.ItemIsEditable))
            self.curFont.setItalic(isSlack)
            self.curFont.setBold(isTodo)
            twi.setFont(self.curFont)
            table.setItem(rowIndex, i, twi)
        self.resizeTable(table)
        return

    def instructionsButtonClicked(self):
        QtGui.QMessageBox.information(0, "Instructions", self.INSTRUCTION_TEXT_STR)
        return

    def dirBrowseButtonClicked(self):
        browse_dir = QtGui.QFileDialog.getExistingDirectory()
        if "" <> browse_dir:
            self.dirEdit.setText(browse_dir)
        return

    def str2tripint(self, s):
        tripint = map(long, re.findall(r"[\w']+", s))
        assert(len(tripint) == 3)
        return tripint

    def tripintadd(self, a, b):
        assert(len(a) == len(b))
        return [(a[i]+b[i]) for i in xrange(len(a))]

    def validateDir(self, s):
        if s[-1] <> "/":
            s += "/"
        assert(os.path.isdir(s))
        return s

    def nextId(self):
        return max(self.mapIdToCoord.keys() + [self.baseSubObjId - 1]) + 1

    def firstId(self):
        l = self.mapIdToCoord.keys()
        if len(l) == 0:
            return self.invalidId
        return min(l)

    def IdFromRow(self, isDone, row):
        table = self.tableHash[isDone]["Table"]
        if (row > table.rowCount) or (row < 0):
            return self.invalidId
        return long(table.item(row,0).text())

    def RowFromId(self, isDone, Id):
        table = self.tableHash[isDone]["Table"]
        for row in xrange(table.rowCount):
            if self.IdFromRow(isDone, row) == Id:
                return row
        return self.invalidRow

    def pushTableStackId(self, isDone, Id, atFirst = False):
        stack = self.tableHash[isDone]["Stack"]
        if len(stack) == 0:
            stack.append(Id)
            return self.invalidId
        prevLastId = stack[-1]
        if prevLastId <> Id:
            if Id in stack:
                stack.remove(Id)
            if atFirst:
                stack[:0] = [Id]
            else:
                stack.append(Id)
        return prevLastId

    def popTableStackId(self, isDone, Id):
        stack = self.tableHash[isDone]["Stack"]
        if Id in stack:
            stack.remove(Id)
        if len(stack) == 0:
            return self.invalidId
        return stack[-1]

    def IsInvalidId(self,Id):
        return (Id == self.invalidId)

    def IsSlackId(self,Id):
        return (Id == self.slackObjId)

    def IsNormalId(self,Id):
        return not (self.IsSlackId(Id) or self.IsInvalidId(Id))

    def setActiveNode(self):
        Id = self.curObjId
        if self.IsNormalId(Id):
            skeleton.set_active_node(self.mapIdToNodeId[Id])
        return

    def selectObjId(self, Id):
        if Id <> self.curObjId:
            self.undoButtonClicked()
        self.curObjId = Id
        self.applyMask()
        self.setActiveNode()
        self.jumpToId(Id)
        return

    def isSlackCheckBoxChanged(self,state):
        self.slackErosionItersEdit.enabled = (state == Qt.Qt.Checked)
        return

    def getTableSelectedRow(self,table):
        return [x.row() for x in table.selectionModel().selectedRows()]
    
    def tableSelectionChangedCommon(self,isDone):
        if not self.active:
            return
        if self.onChange:
            return
        table = self.tableHash[isDone]["Table"]
        rows = self.getTableSelectedRow(table)
        if len(rows) <> 1:
            return
        self.tableClickByRow(isDone,rows[0])
        return

    def pendSubObjTableSelectionChanged(self):
        isDone = False
        self.tableSelectionChangedCommon(isDone)
        return

    def doneSubObjTableSelectionChanged(self):
        isDone = True
        self.tableSelectionChangedCommon(isDone)
        return

    def selectRowWrap(self,table,row):
        self.onChange = True
        table.selectRow(row)
        self.onChange = False
        return

    def pendSubObjTableCellClicked(self, row, col):
        isDone = False
        table = self.tableHash[isDone]["Table"]
        Id = self.IdFromRow(isDone, row)
        prev = self.pushTableStackId(isDone, Id)
        if prev <> Id:
            self.selectRowWrap(table,row)
        if self.curObjId == Id:
            self.jumpToId(Id)
            return
        self.selectObjId(Id)
        return

    def tableClickByRow(self,isDone,row):
        clickF = self.tableHash[isDone]["Click"]
        clickF(row,0)
        return
    
    def tableDoubleClickByRow(self,isDone,row):
        doubleClickF = self.tableHash[isDone]["DoubleClick"]
        doubleClickF(row,0)
        return
    
    def tableClickById(self,Id):
        isDone = self.mapIdToDone[Id]
        row = self.RowFromId(isDone,Id)
        self.tableClickByRow(isDone,row)
        return

    def tableDoubleClickById(self,Id):
        isDone = self.mapIdToDone[Id]
        row = self.RowFromId(isDone,Id)
        self.tableDoubleClickByRow(isDone,row)
        return

    def stackTop(self,isDone):
        stack = self.tableHash[isDone]["Stack"]
        if len(stack) == 0:
            return self.invalidId
        return stack[-1]

    def clickTop(self,isDone):
        stackTopId = self.stackTop(isDone)
        if stackTopId == self.invalidId:
            return False
        self.tableClickById(stackTopId)
        return True

    def clickTopOrOtherTop(self,isDone):
        if not self.clickTop(isDone):
            self.clickTop(not isDone)
        return

    def tableCellDoubleClickedCommon(self, srcIsDone, row):
        destIsDone = not srcIsDone
        Id = self.IdFromRow(srcIsDone, row)
        self.mapIdToDone[Id] = not self.mapIdToDone[Id]
        self.popTableStackId(srcIsDone,Id)
        self.pushTableStackId(destIsDone,Id)
        self.refreshTables()
        return

    def pendSubObjTableCellDoubleClicked(self, row, col):
        isDone = False
        self.tableCellDoubleClickedCommon(isDone, row)
        self.clickTopOrOtherTop(isDone)
        return

    def doneSubObjTableCellClicked(self, row, col):
        isDone = True
        self.jumpToId(self.IdFromRow(isDone,row))
        return

    def doneSubObjTableCellDoubleClicked(self, row, col):
        isDone = True
        self.tableCellDoubleClickedCommon(isDone, row)
        self.noApplyMask = True
        self.clickTop(isDone)
        self.noApplyMask = False
        self.clickTop(not isDone)
        return
    
    def applyMask(self):
        if self.noApplyMask:
            return
        busyScope = self.BusyCursorScope()
        self.WS_mask = (self.WS == self.curObjId)
        self.WS_masked.fill(0)
        self.WS_masked[self.WS_mask] = self.WS[self.WS_mask]
        self.writeWS(self.WS_masked)
        return

    def TreeIdById(self,Id):
        if Id in self.mapIdToTreeId:
            return self.mapIdToTreeId[Id]
        treeId = skeleton.findAvailableTreeID()
        skeleton.add_tree(treeId)
        self.mapIdToTreeId[Id] = treeId
        return treeId

    def IsMoreCoords(self):
        return (len(self.moreCoords) > 0)

    def addMoreCoords(self, coord, coord_offset, vpId):
        if not self.IsMoreCoords():
            self.undoButton.enabled = True
        self.moreCoords.append((coord,coord_offset,vpId))
        self.addNode(coord, self.TreeIdById(self.nextId()), vpId)
        return

    def seedMatrixDelId(self,Id):
        for coordTuple in self.mapIdToSeedTuples[Id]:
            coord_offset = coordTuple[1]
            self.seedMatrix[coord_offset] = 0
        del self.mapIdToSeedTuples[Id]
        return

    def seedMatrixSetId(self,coordTuples,Id):
        for coordTuple in coordTuples:
            coord_offset = coordTuple[1]
            self.seedMatrix[coord_offset] = Id
        self.mapIdToSeedTuples[Id] = coordTuples
        return

    def addNode(self,coord,treeId,vpId):
        nodeId = skeleton.findAvailableNodeID()
        skeleton.add_node(*((nodeId,)+coord+(treeId,self.markerRadius,vpId,)))
        self.setActiveNode()
        return nodeId

    def addSeedGetParentIds(self,coords):
        parentIds = {}
        for curCoord in coords:
            Id = self.WS[curCoord[1]]
            if (Id <> self.invalidId) and (Id <> self.slackObjId):
                parentIds[Id] = True
        return parentIds.keys()

    def displayCoord(self,coord):
        return tuple(numpy.array(coord)+1)

    def addSeed(self, coord, coord_offset, vpId, isSlack=False):
        Id = self.nextId()
        if (self.lastObjId <> self.invalidId) and (self.curObjId == self.invalidId):
            QtGui.QMessageBox.information(0, "Error", "Select seed first!")
        coordTuples = [(coord, coord_offset, vpId)] + self.moreCoords
        self.seedMatrixSetId(coordTuples,Id)
        parentIds = self.addSeedGetParentIds(coordTuples)
        WS_temp = self.calcWS()
        newObjSize = self.countVal(WS_temp,Id)
        if newObjSize < self.minObjSize:
            QtGui.QMessageBox.information(0, "Error", "New object size (%d) too small!" % newObjSize)
            self.seedMatrixDelId(Id)
            return
        for parentId in parentIds:
            parentObjSize = self.countVal(WS_temp,parentId)
            if parentObjSize < self.minObjSize:
                QtGui.QMessageBox.information(0, "Error", "Parent object (%d) new size (%d) too small!" % (parentId, parentObjSize))
                self.seedMatrixDelId(Id)
                return
        self.WS[self.WS_mask] = WS_temp[self.WS_mask]
        isDone = False
        self.mapCoordToId[coord] = Id
        self.mapIdToSlack[Id] = isSlack
        self.mapIdToTodo[Id] = False
        self.mapIdToCoord[Id] = coord
        self.mapIdToDone[Id] = isDone
        self.mapIdToNodeId[Id] = self.addNode(coord,self.TreeIdById(Id),vpId)
        self.mapIdToMoreCoords[Id] = [curCoord[0] for curCoord in self.moreCoords]
        self.moreCoords = []
        self.undoButton.enabled = False
        self.pushTableStackId(isDone,Id,atFirst=True)
        self.refreshTable(isDone)
        self.noApplyMask = True
        if self.lastObjId == self.invalidId:
            self.clickTop(isDone)
        self.lastObjId = Id
        self.noApplyMask = False
        self.applyMask()
        return

    def refreshTable(self, isDone):
        table = self.tableHash[isDone]["Table"]
        self.clearTable(isDone)
        for (Id,coord) in self.getSortedMapItems():
            if self.mapIdToDone[Id] == isDone:
                self.addTableRow(table, [str(Id), str(self.displayCoord(coord)), str(map(self.displayCoord,self.mapIdToMoreCoords[Id]))],\
                                 self.mapIdToSlack[Id], self.mapIdToTodo[Id], atEnd = True)
        stackTopId = self.stackTop(isDone)
        if stackTopId <> self.invalidId:
            self.selectRowWrap(table,self.RowFromId(isDone, stackTopId))
        return
    
    def removeSeeds(self,Ids):
        if len(Ids) == 0:
            return
        self.noApplyMask = True
        self.noJump = True
        for Id in Ids:
            coordTuples = self.mapIdToSeedTuples[Id]
            self.seedMatrixDelId(Id)
            coord = self.mapIdToCoord[Id]
            del self.mapCoordToId[coord]
            del self.mapIdToCoord[Id]
            isDone = self.mapIdToDone[Id]
            self.popTableStackId(isDone, Id)
            del self.mapIdToDone[Id]
            skeleton.delete_tree(self.mapIdToTreeId[Id])
            del self.mapIdToTreeId[Id]
            del self.mapIdToNodeId[Id]
            del self.mapIdToSlack[Id]
            del self.mapIdToTodo[Id]
            self.refreshTable(isDone)
            self.WS_mask = self.newTrueMatrix()
            self.WS = self.calcWS()
            parentId = self.WS[self.coordOffset(coord)]
            if self.IsInvalidId(parentId):
                Id = self.invalidId
                self.lastObjId = Id
                self.selectObjId(Id)
            else:
                if self.mapIdToDone[parentId]:
                    self.tableDoubleClickById(parentId)
                    return
                self.pushTableStackId(isDone,parentId)
            self.refreshTable(isDone)
            self.clickTopOrOtherTop(isDone)
        self.noJump = False
        self.jumpToCoord(coord)
        self.noApplyMask = False
        self.applyMask()
        return

    def tableDel(self,isDone):
        table = self.tableHash[isDone]["Table"]
        rows = self.getTableSelectedRow(table)
        if len(rows) == 0:
            return
        Ids = []
        slackError = False
        for row in rows:
            Id = self.IdFromRow(isDone,row)
            if self.IsSlackId(Id):
                slackError = True
                continue
            Ids.append(Id)
        self.removeSeeds(Ids)
        if slackError:
            QtGui.QMessageBox.information(0, "Error", "Auto slack cannot be removed")
        return

    def tableS(self,isDone):
        table = self.tableHash[isDone]["Table"]
        rows = self.getTableSelectedRow(table)
        if len(rows) == 0:
            return
        slackError = False
        for row in rows:
            Id = self.IdFromRow(isDone,row)
            if self.IsSlackId(Id):
                slackError = True
                continue
            self.mapIdToSlack[Id] = not self.mapIdToSlack[Id]
        self.refreshTable(isDone)
        if slackError:
            QtGui.QMessageBox.information(0, "Error", "Cannot toggle auto slack!")
        return

    def tableCtrlB(self,isDone):
        table = self.tableHash[isDone]["Table"]
        rows = self.getTableSelectedRow(table)
        if len(rows) == 0:
            return
        for row in rows:
            Id = self.IdFromRow(isDone,row)
            self.mapIdToTodo[Id] = not self.mapIdToTodo[Id]
        self.refreshTable(isDone)
        return

    def pendSubObjTableDel(self):
        isDone = False
        self.tableDel(isDone)
        return

    def doneSubObjTableDel(self):
        isDone = True
        self.tableDel(isDone)
        return
    
    def pendSubObjTableS(self):
        isDone = False
        self.tableS(isDone)
        return

    def doneSubObjTableS(self):
        isDone = True
        self.tableS(isDone)
        return

    def pendSubObjTableCtrlB(self):
        isDone = False
        self.tableCtrlB(isDone)
        return

    def doneSubObjTableCtrlB(self):
        isDone = True
        self.tableCtrlB(isDone)
        return

    def refreshTables(self):
        map(self.refreshTable, [False,True])
        return

    def getSortedMapItems(self):
        IdCoordTuples = self.mapIdToCoord.items()
        IdCoordTuples.sort()
        return IdCoordTuples

    def jumpToCoord(self, coord):
        if self.noJump:
            return
        self.setPositionWrap(coord)
        return

    def waitForLoader(self):
        busyScope = self.BusyCursorScope()
        while knossos.loaderDownloadCount() > 0:
            Qt.QApplication.processEvents()
            time.sleep(0)
        return

    def setPositionWrap(self, coord):
        curNum = knossos.loaderLoadingNr()
        knossos.setPosition(coord)
        newNum = knossos.loaderLoadingNr()
        if curNum == newNum:
            return
        self.waitForLoader()
        return

    def jumpToId(self, Id):
        if self.IsNormalId(Id):
            coord = self.mapIdToCoord[Id]
            self.jumpToCoord(coord)
        return

    def coordOffset(self,coord):
        return tuple(self.margin + numpy.array(coord) - self.knossos_beginCoord_arr)

    def calcWS(self,isSlack=False):
        busyScope = self.BusyCursorScope()
        seededDist = self.distMemPred-((self.seedMatrix > 0)*1.0)
        if isSlack:
            mask = self.newTrueMatrix()
        else:
            mask = self.WS_mask
        ws = watershed(seededDist, self.seedMatrix, None, None, mask)
        return ws
    
    def countVal(self,matrix,val):
        return numpy.sum(matrix==val)

    def isEmpty(self):
        return len(self.mapCoordToId) == 0

    def handleMouseReleaseMiddle(self, eocd, clickedCoord, vpId, event):
        if not self.active:
            return
        coord = tuple(clickedCoord.vector())
        coord_offset = self.coordOffset(coord)
        if self.WS_mask[coord_offset] == False:
            self.jumpToId(self.WS[coord_offset])
            return
        if self.seedMatrix[coord_offset] <> 0:
            
            return
        mods = event.modifiers()
        if mods == 0:
            t = time.time()
            self.addSeed(coord,coord_offset,vpId)
        elif mods == Qt.Qt.ShiftModifier:
            self.addMoreCoords(coord,coord_offset,vpId)
        elif mods == Qt.Qt.ControlModifier:
            self.addSeed(coord,coord_offset,vpId,isSlack=True)
        return

    def undoButtonClicked(self):
        if not self.IsMoreCoords():
            return
        skeleton.delete_tree(self.mapIdToTreeId.pop(self.nextId()))
        self.setActiveNode()
        self.moreCoords = []
        self.undoButton.enabled = False
        return

    def flatCoordsToCoords(self, flatCubeCoords):
        l = []
        flatCubeCoords = list(flatCubeCoords)
        coordLen = len(flatCubeCoords)
        assert(coordLen % 3 == 0)
        for i in xrange(0,coordLen,3):
            l.append(tuple(flatCubeCoords[i:i+3]))
        return l

    def coordsToFlatCoords(self, coords):
        l = []
        for coord in coords:
            assert(len(coord) == 3)
            l += coord
        return l

    def npDataPtr(self, matrix):
        return matrix.__array_interface__["data"][0]

    def accessMatrix(self, matrix, isWrite):
        self.waitForLoader()
        return knossos.processRegionByStridedBufProxy(list(self.knossos_beginCoord_arr), list(self.knossos_dims_arr), self.npDataPtr(matrix), matrix.strides, isWrite, True)

    def writeMatrix(self, matrix):
        self.accessMatrix(matrix, True)
        return

    def matrixNoMargin(self,matrix):
        return matrix[self.margin:-self.margin,self.margin:-self.margin,self.margin:-self.margin]

    def writeWS(self, matrix):
        self.writeMatrix(self.matrixNoMargin(matrix))

    def newMatrix(self,dims=None,dtype=None):
        if dims == None:
            dims = self.dims_arr
        if dtype == None:
            dtype = "uint64"
        return numpy.ndarray(shape=dims, dtype=dtype)

    def newValMatrix(self, val, dtype=None):
        matrix = self.newMatrix(dtype=dtype)
        matrix.fill(val)
        return matrix

    def newTrueMatrix(self):
        return self.newValMatrix(True,dtype="bool")

    def readMatrix(self, matrix):
        self.accessMatrix(matrix, False)
        return

    def commonEnd(self):
        knossos.resetMovementArea()
        self.active = False
        map(self.clearTable,[False,True])
        for treeId in self.mapIdToTreeId.values():
            skeleton.delete_tree(treeId)
        self.guiEnd()
        self.endMatrices()
        return
    
    def guiBegin(self):
        self.confWidgetWidthEdit.text = str(self.size.width())
        self.confWidgetHeightEdit.text = str(self.size.height())
        self.configGroupBox.hide()
        self.widgetLayout.addWidget(self.subObjTableGroupBox)
        self.subObjTableGroupBox.show()
        self.beginButton.enabled = False
        self.resetButton.enabled = True
        self.finishButton.enabled = True
        self.onChange = False
        self.undoPrevEnabled = False
        Qt.QApplication.processEvents()
        self.resize(int(self.workWidgetWidthEdit.text),int(self.workWidgetHeightEdit.text))
        return

    def guiEnd(self):
        self.workWidgetWidthEdit.text = str(self.size.width())
        self.workWidgetHeightEdit.text = str(self.size.height())
        self.configGroupBox.show()
        self.widgetLayout.removeWidget(self.subObjTableGroupBox)
        self.subObjTableGroupBox.hide()
        self.beginButton.enabled = True
        self.undoButton.enabled = False
        self.resetButton.enabled = False
        self.finishButton.enabled = False
        Qt.QApplication.processEvents()
        self.resize(int(str(self.confWidgetWidthEdit.text)),int(str(self.confWidgetHeightEdit.text)))
        return

    def scaleMatrix(self,m,minVal,maxVal):
        curMinVal = m.min()
        curRange = m.max() - curMinVal
        newRange = maxVal - minVal
        return ((m - curMinVal)*(newRange/curRange))+minVal

    def beginMatrices(self):
        self.noApplyMask = False
        self.orig = self.newMatrix(dims=self.knossos_dims_arr)
        self.readMatrix(self.orig)
        self.WS = self.newValMatrix(self.invalidId)
        self.WS_mask = self.newTrueMatrix()
        self.WS_masked = self.newValMatrix(self.invalidId)
        self.memPred = self.loadMembranePrediction(self.validateDir(str(self.dirEdit.text)), self.beginCoord_arr, self.dims_arr)
        pad = 1
        self.memPred = numpy.pad(self.memPred,((pad,pad),)*3,'constant',constant_values=((0,0),)*3)
        self.distMemPred = -ndimage.distance_transform_edt(self.memPred)
        if self.isSlack:
            self.distMemPred += -ndimage.distance_transform_edt(numpy.invert(self.memPred))
            if self.slackErosionIters == 0:
                erosion = numpy.invert(self.memPred)
            else:
                erosion = ndimage.morphology.binary_erosion(numpy.invert(self.memPred), iterations=self.slackErosionIters)
            self.seedMatrix = erosion * self.slackObjId
            self.seedMatrix = self.seedMatrix[pad:-pad,pad:-pad,pad:-pad]
        else:
            self.seedMatrix = self.newValMatrix(0)
        self.distMemPred = self.distMemPred[pad:-pad,pad:-pad,pad:-pad]
        self.distMemPred = self.scaleMatrix(self.distMemPred,0,1)
        self.applyMask()
        return

    def endMatrices(self):
        del self.orig
        del self.WS_mask
        del self.WS
        del self.seedMatrix
        del self.memPred
        del self.distMemPred
        return

    def finalizeSubObjs(self):
        if not self.isSlack:
            self.mapIdToCoord[self.slackObjId] = self.slackCoord
        for (Id, coord) in self.mapIdToCoord.items():
            if self.mapIdToSlack[Id] and (not self.IsSlackId(Id)):
                self.WS[self.WS == Id] = self.slackObjId
                continue
            segmentation.subobjectFromId(Id, coord)
            if self.mapIdToTodo[Id]:
                objIndex = segmentation.largestObjectContainingSubobject(Id,(0,0,0))
                segmentation.changeComment(objIndex,"WatershedSplitter")
                pass
        return

    def beginSeeds(self):
        self.noJump = False
        self.curObjId = self.invalidId
        self.lastObjId = self.invalidId
        self.mapCoordToId = {}
        self.mapIdToCoord = {}
        self.mapIdToTreeId = {}
        self.moreCoords = []
        self.mapIdToMoreCoords = {}
        self.mapIdToNodeId = {}
        self.mapIdToSlack = {}
        self.mapIdToTodo = {}
        self.mapIdToSeedTuples = {}
        self.mapIdToDone = {}
        return
    
    def beginSlack(self):
        Id = self.slackObjId
        self.WS = self.calcWS()
        isDone = False
        coord = self.slackCoord
        self.mapCoordToId[coord] = Id
        self.mapIdToCoord[Id] = coord
        self.mapIdToDone[Id] = isDone
        self.mapIdToSlack[Id] = True
        self.mapIdToTodo[Id] = False
        self.mapIdToMoreCoords[Id] = []
        self.refreshTable(isDone)
        self.lastObjId = self.slackObjId
        self.pendSubObjTableCellClicked(0,0)
        self.applyMask()
        return
    
    def beginButtonClicked(self):
        retVal = True
        try:
            self.slackObjId = 1L
            self.slackCoord = (-1,-1,-1)
            self.invalidId = 0L
            assert(self.slackObjId <> self.invalidId)
            self.invalidRow = -1
            # parse edits
            self.margin = int(self.marginEdit.text)
            self.knossos_dims_arr = numpy.array(self.str2tripint(str(self.workAreaSizeEdit.text)))
            self.dims_arr = self.knossos_dims_arr + (2*self.margin)
            self.baseSubObjId = long(str(self.baseSubObjIdEdit.text))
            self.markerRadius = int(self.markerRadiusEdit.text)
            self.minObjSize = int(self.minObjSizeEdit.text)
            self.memThres = int(self.memThresEdit.text)
            self.isSlack = self.isSlackCheckBox.isChecked()
            self.slackErosionIters = int(self.slackErosionItersEdit.text)
            self.knossos_beginCoord_arr = numpy.array(self.str2tripint(str(self.workAreaBeginEdit.text)))-numpy.array([1]*3)
            self.beginCoord_arr = self.knossos_beginCoord_arr - self.margin
            self.knossos_endCoord_arr = self.knossos_beginCoord_arr + self.knossos_dims_arr - 1
            self.setPositionWrap(tuple((self.knossos_beginCoord_arr + self.knossos_endCoord_arr) / 2))
            self.beginSeeds()
            self.beginMatrices()
            knossos.setMovementArea(list(self.knossos_beginCoord_arr), list(self.knossos_endCoord_arr))
            self.tableHash = {True:{"Stack":[],"Table":self.doneSubObjTable,"Click":self.doneSubObjTableCellClicked,"DoubleClick":self.doneSubObjTableCellDoubleClicked},\
                              False:{"Stack":[],"Table":self.pendSubObjTable,"Click":self.pendSubObjTableCellClicked,"DoubleClick":self.pendSubObjTableCellDoubleClicked}}
            self.guiBegin()
            if self.isSlack:
                self.beginSlack()
            self.active = True
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            inf = "\n".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            QtGui.QMessageBox.information(0, "Error", "Exception caught!\n" + inf)
            retVal = False
        return retVal
    
    def resetButtonClicked(self):
        self.writeMatrix(self.orig)
        self.commonEnd()
        return

    def finishButtonClicked(self):
        self.finalizeSubObjs()
        self.writeWS(self.WS)
        self.commonEnd()
        return

    def exportMatrix(self,matrix,p,noMargin):
        try:
            os.makedirs(p)
        except:
            pass
        if noMargin:
            matrix = self.matrixNoMargin(matrix)
        for z in xrange(0, matrix.shape[2]):
            img = Image.fromarray(matrix[:,:,z].transpose())
            img.save(os.path.join(p,str(z)+'.tif'))
        return

    def exportDist(self,p,noMargin=False):
        return self.exportMatrix(self.distMemPred,p,noMargin)

    def exportSeeds(self,p,noMargin=False):
        return self.exportMatrix(self.seedMatrix,p,noMargin)

    def exportWS(self,p,noMargin=False):
        return self.exportMatrix(self.WS,p,noMargin)

    pass

plugin_container.append(watershedSplitter())
