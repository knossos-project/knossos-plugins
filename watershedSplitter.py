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
- Subobject ID and comment for slack
- Beginning and size of work area as an x,y,z blank-separated tuples
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
        self.twiHeadersList = []
        self.twiHash = {}
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
        subObjTableLayout = QtGui.QHBoxLayout()
        subObjTableGroupBox.setLayout(subObjTableLayout)
        self.subObjTable = QtGui.QTableWidget()
        subObjTableLayout.addWidget(self.subObjTable)
        self.setTableHeaders(self.subObjTable, self.OBJECT_LIST_COLUMNS)
        self.subObjTable.cellClicked.connect(self.subObjTableCellClicked)
        self.finalizeTable(self.subObjTable)
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
        for (edit,key,default) in self.settings:
            val = settings.value(key)
            if (val == None) or (str(val)==""):
                val_str = default
            else:
                val_str = str(val)
            edit.text = val_str
        settings.endGroup()
        return

    def saveConfig(self):
        settings = Qt.QSettings()
        settings.beginGroup(self.pluginConf)
        for (edit,key,default) in self.settings:
            settings.setValue(key,str(edit.text))
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
                        (self.markerRadiusEdit,"MARKER_RADIUS","10"), \
                        (self.memThresEdit,"MEM_THRES","150"), \
                        (self.minObjSizeEdit,"MIN_OBJ_SIZE","500")]
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
        self.finishButtonClicked()
        self.uninitLogic()
        event.accept()
        return
    
    def closeEventNo(self,event):
        self.resetButtonClicked()
        self.uninitLogic()
        event.accept()
        return
    
    def closeEventAbort(self,event):
        event.ignore()
        return
    
    def closeEvent(self,event):
        if not self.active:
            self.uninitLogic()
            event.accept()
            return
        mb = QtGui.QMessageBox()
        yes = QtGui.QMessageBox.No; no = QtGui.QMessageBox.No; abort = QtGui.QMessageBox.Abort
        mb.setStandardButtons(yes | no | abort)
        action = {yes: self.closeEventYes, no: self.closeEventNo, abort: self.closeEventAbort}
        action[mb._exec(self, "Closing while active!", "Save?", yes|no|abort)](event);
        return

    def setTableHeaders(self, table, columnNames):
        columnNum = len(columnNames)
        table.setColumnCount(columnNum)
        for i in xrange(columnNum):
            twi = QtGui.QTableWidgetItem(columnNames[i])
            table.setHorizontalHeaderItem(i, twi)
            self.twiHeadersList.append(twi)
        return

    def clearTable(self, table):
        table.clearContents()
        del self.twiHash.setdefault(table,[])[:]
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
            self.twiHash.setdefault(table,[]).append(twi)
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
            return -1
        return min(l)

    def subObjTableCellClicked(self, row, col):
        Id = long(self.subObjTable.item(row,0).text())
        self.setCurObjId(Id)
        return

    def jumpToId(self, Id):
        coord = self.mapIdToCoord[Id]
        knossos.setPosition(coord)
        return

    def setCurObjId(self,Id):
        self.jumpToId(Id)
        if Id == self.curObjId:
            return
        self.undoButton.enabled = False
        self.prevObjId = self.curObjId
        self.curObjId = Id
        if Id <> self.slackObjId:
            skeleton.set_active_node(self.subObjIdToNodeId(Id))
        self.applyMask()
        return

    def coordOffset(self,coord):
        return tuple(numpy.array(coord)-self.beginCoord_arr)

    def calcWS(self):
        return watershed(self.slackMemPred, self.seedMatrix, None, None, self.WS_mask)

    def countVal(self,matrix,val):
        return numpy.sum(matrix==val)

    def isEmpty(self):
        return len(self.mapCoordToId) == 0

    def getObjIdTableRow(self, Id):
        for row in xrange(self.subObjTable.rowCount):
            if Id == long(self.subObjTable.item(row,0).text()):
                return row
        return -1

    def reselectObjId(self, Id):
        # ERASE?
        self.setCurObjId(Id)
        self.subObjTable.selectRow(self.getObjIdTableRow(Id))
        return
    
    def addSeed(self, coord, vpId):
        coord_offset = self.coordOffset(coord)
        Id = self.nextId()
        if self.WS_mask[coord_offset] == False:
            self.jumpToId(self.WS[coord_offset])
            return
        self.seedMatrix[coord_offset] = Id
        parentId = self.WS[coord_offset]
        WS_temp = self.calcWS()
        if min(self.countVal(WS_temp,Id), self.countVal(WS_temp,parentId)) < self.minObjSize:
            QtGui.QMessageBox.information(0, "Error", "Object too small!")
            self.seedMatrix[coord_offset] = 0
            return
        self.lastObjId = Id
        self.WS[self.WS_mask] = WS_temp[self.WS_mask]
        self.mapCoordToId[coord] = Id
        self.mapIdToCoord[Id] = coord
        skeleton.add_node(*((Id,)+coord+(self.MAGIC_TREE_NUM,self.markerRadius,vpId,)))
        rowSelection = self.refreshTable()
        self.applyMask()
        self.subObjTable.selectRow(rowSelection)
        self.undoButton.enabled = True
        return

    def getSortedMapItems(self):
        IdCoordTuples = self.mapIdToCoord.items()
        IdCoordTuples.sort()
        return IdCoordTuples
    
    def refreshTable(self):
        row = self.subObjTable.currentRow()
        self.clearTable(self.subObjTable)
        for (Id,coord) in self.getSortedMapItems():
            self.addTableRow(self.subObjTable, [str(Id), str(coord)], atEnd = True)
        return row

    def removeSeed(self,Id):
        coord = self.mapIdToCoord[Id]
        self.seedMatrix[self.coordOffset(coord)] = 0
        self.WS_mask[:,:,:] = self.WS_mask_prev[:,:,:]
        WS_temp = self.calcWS()
        self.WS[self.WS_mask] = WS_temp[self.WS_mask]
        self.applyMask()
        del self.mapCoordToId[coord]
        del self.mapIdToCoord[Id]
        skeleton.delete_node(Id)
        rowSelection = self.refreshTable()
        self.subObjTable.selectRow(rowSelection)
        return

    def handleMouseReleaseMiddle(self, eocd, clickedCoord, vpId, event):
        if not self.active:
            return
        coord = tuple(clickedCoord.vector())
        self.addSeed(coord,vpId)
        return

    def applyMask(self):
        self.WS_mask_prev[:,:,:] = self.WS_mask[:,:,:]
        self.WS_mask = (self.WS == self.curObjId)
        self.WS_masked.fill(0)
        self.WS_masked[self.WS_mask] = self.WS[self.WS_mask]
        self.writeMatrix(self.WS_masked)
        return

    def undoButtonClicked(self):
        self.removeSeed(self.lastObjId)
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
        return knossos.processRegionByStridedBufProxy(list(self.beginCoord_arr), list(self.dims_arr), self.npDataPtr(matrix), matrix.strides, isWrite, True)

    def writeMatrix(self, matrix):
        self.accessMatrix(matrix, True)
        return

    def newMatrix(self):
        return numpy.ndarray(shape=self.dims_arr, dtype="uint64")

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
        self.clearTable(self.subObjTable)
        self.guiEnd()
        self.endMatrices()
        return
    
    def guiBegin(self):
        self.configGroupBox.enabled = False
        self.beginButton.enabled = False
        self.resetButton.enabled = True
        self.finishButton.enabled = True
        return

    def guiEnd(self):
        self.configGroupBox.enabled = True
        self.beginButton.enabled = True
        self.undoButton.enabled = False
        self.resetButton.enabled = False
        self.finishButton.enabled = False
        return

    def beginMatrices(self):
        self.memPred = self.loadMembranePrediction(self.validateDir(str(self.dirEdit.text)), self.beginCoord_arr, self.dims_arr)
        self.orig = self.newValMatrix(0)
        self.readMatrix(self.orig)
        self.WS = self.newValMatrix(0)
        self.WS_mask = (self.WS == 0)
        self.WS_mask_prev = (self.WS == 0)
        self.WS_masked = self.newValMatrix(0)
        self.writeMatrix(self.WS)
        return

    def endMatrices(self):
        del self.orig
        del self.WS
        del self.seedMatrix
        del self.memPred
        return

    def beginSeeds(self):
        self.mapCoordToId = {}
        self.mapIdToCoord = {}
        self.curObjId = self.slackObjId
        self.prevObjId = -1
        skeleton.add_tree(self.MAGIC_TREE_NUM)
        return

    def applySlack(self):
        dt_objects_ws = -ndimage.distance_transform_edt(self.memPred)
        dt_slack = -ndimage.distance_transform_edt(numpy.invert(self.memPred))
        self.slackMemPred = dt_slack + dt_objects_ws
        # use this matrix and add the manual seeds on top of it
        Id = self.slackObjId
        self.seedMatrix = ndimage.morphology.binary_erosion(numpy.invert(self.memPred), iterations=5) * Id
        # Apply
        WS_temp = self.calcWS()
        self.WS[self.WS_mask] = WS_temp[self.WS_mask]
        coord = (-1,-1,-1)
        self.mapCoordToId[coord] = Id
        self.mapIdToCoord[Id] = coord
        rowSelection = 0
        self.refreshTable()
        self.subObjTableCellClicked(0,0)
        self.applyMask()
        self.subObjTable.selectRow(rowSelection)
        return

    def clickSubObjs(self):
        for (Id, coord) in self.mapIdToCoord.items():
            segmentation.clickSubObj(Id, coord)
        return
    
    def beginButtonClicked(self):
        retVal = True
        try:
            self.slackObjId = 1
            self.dims_arr = numpy.array(self.str2tripint(str(self.workAreaSizeEdit.text)))
            self.baseSubObjId = long(str(self.baseSubObjIdEdit.text))
            self.markerRadius = int(self.markerRadiusEdit.text)
            self.minObjSize = int(self.minObjSizeEdit.text)
            self.memThres = int(self.memThresEdit.text)
            self.beginCoord_arr = numpy.array(self.str2tripint(str(self.workAreaBeginEdit.text)))
            self.endCoord_arr = self.beginCoord_arr + self.dims_arr - 1
            self.beginMatrices()
            self.beginSeeds()
            knossos.setPosition(tuple((self.beginCoord_arr + self.endCoord_arr) / 2))
            knossos.setMovementArea(list(self.beginCoord_arr), list(self.endCoord_arr))
            self.guiBegin()
            self.active = True
            self.applySlack()
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
        self.writeMatrix(self.WS)
        self.clickSubObjs()
        self.commonEnd()
        return

    pass

plugin_container.append(watershedSplitter())
