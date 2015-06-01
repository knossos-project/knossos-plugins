from PythonQt import QtGui, Qt
import DatasetUtils, numpy, os, re, string, sys, traceback
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
    OBJECT_LIST_COLUMNS = [SUBOBJECT_ID_COLUMN_STR, SUBOBJECT_COORD_COLUMN_STR]
    MAGIC_TREE_NUM = 99999999
    
    def initGUI(self):
        self.setWindowTitle("Watershed Splitter")
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        instructionsButton = QtGui.QPushButton("See Instructions")
        instructionsButton.clicked.connect(self.instructionsButtonClicked)
        layout.addWidget(instructionsButton)
        self.configGroupBox = QtGui.QGroupBox("Configuration")
        layout.addWidget(self.configGroupBox)
        configLayout = QtGui.QVBoxLayout()
        self.configGroupBox.setLayout(configLayout)
        layout.addLayout(configLayout)
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
        workAreaLayout.addWidget(QtGui.QLabel("Marker Radius"))
        self.markerRadiusEdit = QtGui.QLineEdit()
        workAreaLayout.addWidget(self.markerRadiusEdit)
        paramsLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(paramsLayout)
        paramsLayout.addWidget(QtGui.QLabel("Base SubObj ID"))
        self.baseSubObjIdEdit = QtGui.QLineEdit()
        paramsLayout.addWidget(self.baseSubObjIdEdit)
        paramsLayout.addWidget(QtGui.QLabel("Membrane Threshold"))
        self.memThresEdit = QtGui.QLineEdit()
        paramsLayout.addWidget(self.memThresEdit)
        paramsLayout.addWidget(QtGui.QLabel("Min Obj Size"))
        self.minObjSizeEdit = QtGui.QLineEdit()
        paramsLayout.addWidget(self.minObjSizeEdit)
        paramsLayout.addWidget(QtGui.QLabel("Use Slack"))
        self.isSlackCheckBox = QtGui.QCheckBox()
        self.isSlackCheckBox.setChecked(False)
        paramsLayout.addWidget(self.isSlackCheckBox)
        opButtonsLayout = QtGui.QHBoxLayout()
        layout.addLayout(opButtonsLayout)
        self.beginButton = QtGui.QPushButton("Begin")
        self.beginButton.clicked.connect(self.beginButtonClicked)
        opButtonsLayout.addWidget(self.beginButton)
        self.undoButton = QtGui.QPushButton("Undo")
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
        subObjTableGroupBox = QtGui.QGroupBox("SubObjects")
        layout.addWidget(subObjTableGroupBox)
        subObjTableLayout = QtGui.QGridLayout()
        subObjTableGroupBox.setLayout(subObjTableLayout)
        self.subObjTable = QtGui.QTableWidget()
        subObjTableLayout.addWidget(QtGui.QLabel("Pending"),0,0)
        subObjTableLayout.addWidget(self.subObjTable,1,0)
        self.setTableHeaders(self.subObjTable, self.OBJECT_LIST_COLUMNS)
        self.subObjTable.cellClicked.connect(self.subObjTableCellClicked)
        self.subObjTable.itemSelectionChanged.connect(self.subObjTableSelectionChanged)
        self.subObjTable.cellDoubleClicked.connect(self.subObjTableCellDoubleClicked)
        self.finalizeTable(self.subObjTable)
        self.doneSubObjTable = QtGui.QTableWidget()
        subObjTableLayout.addWidget(QtGui.QLabel("Done"),0,1)
        subObjTableLayout.addWidget(self.doneSubObjTable,1,1)
        self.setTableHeaders(self.doneSubObjTable, self.OBJECT_LIST_COLUMNS)
        self.doneSubObjTable.cellClicked.connect(self.doneSubObjTableCellClicked)
        self.doneSubObjTable.cellDoubleClicked.connect(self.doneSubObjTableCellDoubleClicked)
        self.finalizeTable(self.doneSubObjTable)
        # Show
        self.setWindowFlags(Qt.Qt.Window)
        self.show()
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
        return numpy.invert(((memPred > self.memThres) * 255).astype(numpy.uint8))

    def finalizeTable(self, table):
        table.horizontalHeader().setStretchLastSection(True)
        self.resizeTable(table)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
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
        # TODO Slack Checkbox
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
                        (self.marginEdit,"MARGIN","10"), \
                        (self.markerRadiusEdit,"MARKER_RADIUS","10"), \
                        (self.memThresEdit,"MEM_THRES","150"), \
                        (self.minObjSizeEdit,"MIN_OBJ_SIZE","500"),
                       (self.isSlackCheckBox,"IS_SLACK",False)]
        self.loadConfig()
        self.signalConns = []
        self.signalConns.append((signalRelay.Signal_EventModel_handleMouseReleaseMiddle, self.handleMouseReleaseMiddle))
        self.signalsConnect()
        return

    def uninitLogic(self):
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

    def clearTable(self, tableIsDone):
        table = self.tableHash[tableIsDone]["Table"]
        table.clearContents()
        table.setRowCount(0)
        return

    def resizeTable(self, table):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        return

    def addTableRow(self, table, columnTexts, atEnd = False):
        rowIndex = 0
        if atEnd:
            rowIndex = table.rowCount
        table.insertRow(rowIndex)
        for i in xrange(len(columnTexts)):
            twi = QtGui.QTableWidgetItem(columnTexts[i])
            twi.setFlags(twi.flags() & (~Qt.Qt.ItemIsEditable))
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

    def subObjIdToNodeId(self,Id):
        return Id

    def nextId(self):
        return max(self.mapIdToCoord.keys() + [self.baseSubObjId - 1]) + 1

    def firstId(self):
        l = self.mapIdToCoord.keys()
        if len(l) == 0:
            return self.invalidId
        return min(l)

    def IdFromRow(self, tableIsDone, row):
        table = self.tableHash[tableIsDone]["Table"]
        if (row > table.rowCount) or (row < 0):
            return self.invalidId
        return long(table.item(row,0).text())

    def RowFromId(self, tableIsDone, Id):
        table = self.tableHash[tableIsDone]["Table"]
        for row in xrange(table.rowCount):
            if self.IdFromRow(tableIsDone, row) == Id:
                return row
        return self.invalidRow

    def pushTableStackId(self, tableIsDone, Id, atFirst = False):
        stack = self.tableHash[tableIsDone]["Stack"]
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

    def popTableStackId(self, tableIsDone, Id):
        stack = self.tableHash[tableIsDone]["Stack"]
        if Id in stack:
            stack.remove(Id)
        if len(stack) == 0:
            return self.invalidId
        return stack[-1]

    def selectObjId(self, Id):
        self.undoButton.enabled = False
        self.curObjId = Id
        self.applyMask()
        if (Id == self.invalidId) or (Id == self.slackObjId):
            return
        skeleton.set_active_node(self.subObjIdToNodeId(Id))
        self.jumpToId(Id)
        return

    def subObjTableSelectionChanged(self):
        if not self.active:
            return
        if self.onChange:
            return
        rows = self.subObjTable.selectionModel().selectedRows()
        if len(rows) == 0:
            return
        row = rows[0].row()
        isDone = False
        if self.curObjId <> self.IdFromRow(isDone,row):
            self.subObjTableCellClicked(row,0)
        return

    def selectRowWrap(self,table,row):
        self.onChange = True
        table.selectRow(row)
        self.onChange = False
        return

    def subObjTableCellClicked(self, row, col):
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

    def tableCellDoubleClickedCommon(self, tableSrcIsDone, row):
        self.undoButton.enabled = False
        tableDestIsDone = not tableSrcIsDone
        tableSrc = self.tableHash[tableSrcIsDone]["Table"]
        tableDest = self.tableHash[tableDestIsDone]["Table"]
        Id = self.IdFromRow(tableSrcIsDone, row)
        self.mapIdToDone[Id] = not self.mapIdToDone[Id]
        return Id

    def subObjTableCellDoubleClicked(self, row, col):
        isDone = False
        Id = self.tableCellDoubleClickedCommon(isDone, row)
        newSrcTopId = self.popTableStackId(isDone,Id)
        self.selectObjId(newSrcTopId)
        self.refreshTables()
        return

    def doneSubObjTableCellClicked(self, row, col):
        isDone = True
        self.jumpToId(self.IdFromRow(isDone,row))
        self.doneSubObjTable.clearSelection()
        self.doneSubObjTable.clearFocus()
        return

    def doneSubObjTableCellDoubleClicked(self, row, col):
        isDone = True
        Id = self.tableCellDoubleClickedCommon(isDone, row)
        prevLastId = self.pushTableStackId(not isDone,Id,atFirst=True)
        self.refreshTables()
        if prevLastId == self.invalidId:
            self.subObjTableCellClicked(self.RowFromId(not isDone, Id),0)
        else:
            self.jumpToId(self.curObjId)
        return
    
    def applyMask(self):
        self.WS_mask_prev[:,:,:] = self.WS_mask[:,:,:]
        self.WS_mask = (self.WS == self.curObjId)
        self.WS_masked.fill(0)
        self.WS_masked[self.WS_mask] = self.WS[self.WS_mask]
        self.writeWS(self.WS_masked)
        return

    def addSeed(self, coord, vpId):
        coord_offset = self.coordOffset(coord)
        Id = self.nextId()
        if self.WS_mask[coord_offset] == False:
            self.jumpToId(self.WS[coord_offset])
            return
        if (self.lastObjId <> self.invalidId) and (self.curObjId == self.invalidId):
            QtGui.QMessageBox.information(0, "Error", "Select seed first!")
        self.seedMatrix[coord_offset] = Id
        parentId = self.WS[coord_offset]
        WS_temp = self.calcWS()
        newObjSize = self.countVal(WS_temp,Id)
        if newObjSize < self.minObjSize:
            QtGui.QMessageBox.information(0, "Error", "New object size (%d) smaller than minimum!" % newObjSize)
            self.seedMatrix[coord_offset] = 0
            return
        if parentId <> self.invalidId:
            parentObjSize = self.countVal(WS_temp,parentId)
            if parentObjSize < self.minObjSize:
                QtGui.QMessageBox.information(0, "Error", "Parent object size (%d) smaller than minimum!" % parentObjSize)
                self.seedMatrix[coord_offset] = 0
                return
        isDone = False
        self.WS[self.WS_mask] = WS_temp[self.WS_mask]
        self.mapCoordToId[coord] = Id
        self.mapIdToCoord[Id] = coord
        self.mapIdToDone[Id] = isDone
        skeleton.add_node(*((Id,)+coord+(self.MAGIC_TREE_NUM,self.markerRadius,vpId,)))
        self.refreshTable(isDone)
        if self.lastObjId == self.invalidId:
            self.subObjTableCellClicked(0,0)
        else:
            self.undoButton.enabled = True
            self.pushTableStackId(isDone,Id,atFirst=True)
        self.lastObjId = Id
        self.applyMask()
        return

    def refreshTable(self, tableIsDone):
        table = self.tableHash[tableIsDone]["Table"]
        self.clearTable(tableIsDone)
        for (Id,coord) in self.getSortedMapItems():
            if self.mapIdToDone[Id] == tableIsDone:
                self.addTableRow(table, [str(Id), str(coord)], atEnd = True)
        stack = self.tableHash[tableIsDone]["Stack"]
        if (len(stack) > 0) and (tableIsDone == False):
            self.selectRowWrap(table,self.RowFromId(tableIsDone, stack[-1]))
        return
    
    def undoSeed(self,Id):
        if Id == self.slackObjId:
            QtGui.QMessageBox.information(0, "Error", "Don't remove slack!")
            return
        coord = self.mapIdToCoord[Id]
        self.seedMatrix[self.coordOffset(coord)] = 0
        self.WS_mask[:,:,:] = self.WS_mask_prev[:,:,:]
        WS_temp = self.calcWS()
        self.WS[self.WS_mask] = WS_temp[self.WS_mask]
        self.applyMask()
        del self.mapCoordToId[coord]
        del self.mapIdToCoord[Id]
        self.popTableStackId(self.mapIdToDone[Id], Id)
        del self.mapIdToDone[Id]
        self.refreshTable(False)
        skeleton.delete_node(Id)
        return

    def refreshTables(self):
        map(self.refreshTable, [False,True])
        return

    def getSortedMapItems(self):
        IdCoordTuples = self.mapIdToCoord.items()
        IdCoordTuples.sort()
        return IdCoordTuples

    def jumpToId(self, Id):
        coord = self.mapIdToCoord[Id]
        knossos.setPosition(coord)
        return

    def coordOffset(self,coord):
        return tuple(self.margin + numpy.array(coord) - self.knossos_beginCoord_arr)

    def calcWS(self):
        return watershed(self.distMemPred, self.seedMatrix, None, None, self.WS_mask)

    def countVal(self,matrix,val):
        return numpy.sum(matrix==val)

    def isEmpty(self):
        return len(self.mapCoordToId) == 0

    def handleMouseReleaseMiddle(self, eocd, clickedCoord, vpId, event):
        if not self.active:
            return
        coord = tuple(clickedCoord.vector())
        self.addSeed(coord,vpId)
        return

    def undoButtonClicked(self):
        self.undoSeed(self.lastObjId)
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
        return knossos.processRegionByStridedBufProxy(list(self.knossos_beginCoord_arr), list(self.knossos_dims_arr), self.npDataPtr(matrix), matrix.strides, isWrite, True)

    def writeMatrix(self, matrix):
        self.accessMatrix(matrix, True)
        return

    def writeWS(self, matrix):
        self.writeMatrix(matrix[self.margin:-self.margin,self.margin:-self.margin,self.margin:-self.margin])

    def newMatrix(self,dims=None):
        if dims == None:
            dims = self.dims_arr
        return numpy.ndarray(shape=dims, dtype="uint64")

    def newValMatrix(self, val):
        matrix = self.newMatrix()
        matrix.fill(val)
        return matrix

    def readMatrix(self, matrix):
        self.accessMatrix(matrix, False)
        return

    def commonEnd(self):
        skeleton.delete_tree(self.MAGIC_TREE_NUM)
        knossos.resetMovementArea()
        self.active = False
        map(self.clearTable,[False,True])
        self.guiEnd()
        self.endMatrices()
        return
    
    def guiBegin(self):
        self.configGroupBox.enabled = False
        self.beginButton.enabled = False
        self.resetButton.enabled = True
        self.finishButton.enabled = True
        self.onChange = False
        return

    def guiEnd(self):
        self.configGroupBox.enabled = True
        self.beginButton.enabled = True
        self.undoButton.enabled = False
        self.resetButton.enabled = False
        self.finishButton.enabled = False
        return

    def beginMatrices(self):
        self.orig = self.newMatrix(dims=self.knossos_dims_arr)
        self.readMatrix(self.orig)
        self.WS = self.newValMatrix(self.invalidId)
        self.WS_mask = (self.WS == self.invalidId)
        self.WS_mask_prev = (self.WS == self.invalidId)
        self.WS_masked = self.newValMatrix(self.invalidId)
        self.memPred = self.loadMembranePrediction(self.validateDir(str(self.dirEdit.text)), self.beginCoord_arr, self.dims_arr)
        self.distMemPred = -ndimage.distance_transform_edt(self.memPred)
        if self.isSlack:
            self.distMemPred += -ndimage.distance_transform_edt(numpy.invert(self.memPred))
            # use this matrix and add the manual seeds on top of it
            self.seedMatrix = ndimage.morphology.binary_erosion(numpy.invert(self.memPred), iterations=5) * self.slackObjId
        else:
            self.seedMatrix = self.newValMatrix(0)
        self.writeWS(self.WS)
        return

    def endMatrices(self):
        del self.orig
        del self.WS_mask
        del self.WS_mask_prev
        del self.WS
        del self.seedMatrix
        del self.memPred
        del self.distMemPred
        return

    def clickSubObjs(self):
        for (Id, coord) in self.mapIdToCoord.items():
            segmentation.clickSubObj(Id, coord)
        return

    def beginSeeds(self):
        self.curObjId = self.invalidId
        self.lastObjId = self.invalidId
        self.mapCoordToId = {}
        self.mapIdToCoord = {}
        self.mapIdToDone = {}
        skeleton.add_tree(self.MAGIC_TREE_NUM)
        return
    
    def beginSlack(self):
        Id = self.slackObjId
        coord = (-1,-1,-1)
        self.WS = self.calcWS()
        isDone = False
        self.mapCoordToId[coord] = Id
        self.mapIdToCoord[Id] = coord
        self.mapIdToDone[Id] = isDone
        self.refreshTable(isDone)
        self.lastObjId = self.slackObjId
        self.subObjTableCellClicked(0,0)
        self.applyMask()
        return
    
    def beginButtonClicked(self):
        retVal = True
        try:
            self.slackObjId = 1
            self.invalidId = 0
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
            self.knossos_beginCoord_arr = numpy.array(self.str2tripint(str(self.workAreaBeginEdit.text)))
            self.beginCoord_arr = self.knossos_beginCoord_arr - self.margin
            self.knossos_endCoord_arr = self.knossos_beginCoord_arr + self.knossos_dims_arr - 1
            self.beginMatrices()
            knossos.setPosition(tuple((self.knossos_beginCoord_arr + self.knossos_endCoord_arr) / 2))
            knossos.setMovementArea(list(self.knossos_beginCoord_arr), list(self.knossos_endCoord_arr))
            self.tableHash = {True:{"Stack":[],"Table":self.doneSubObjTable},False:{"Stack":[],"Table":self.subObjTable}}
            self.guiBegin()
            self.beginSeeds()
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
        self.writeWS(self.WS)
        self.clickSubObjs()
        self.commonEnd()
        return

    pass

plugin_container.append(watershedSplitter())
