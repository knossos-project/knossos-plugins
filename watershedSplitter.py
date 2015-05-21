from PythonQt import QtGui, Qt
import DatasetUtils, numpy, os, re, string, sys, traceback
from scipy import ndimage
from skimage.morphology import watershed
DatasetUtils._set_noprint(True)

#KNOSSOS_PLUGIN Name WatershedSplitter
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Iteratively split a volume into subobjects using a watershed algorithm on a pre-calculated prediction

class watershedSplitter(QtGui.QWidget):
    INSTRUCTION_TEXT_STR = """Fill configuration:
- Pick membrane prediction dataset by browsing to directory of knossos.conf
- Base subobject ID for subobjects to be created
- Size of work area as an x,y,z blank-separated tuple. Do not exceed supercube, stay in mag1

Operation:
- Middle-click center coordinate to begin. This would confine movement
  to work area around it and clean preexisting data
- Iteratively:
-- Middle-click a coordinate inside a subobject to calculate watershed
-- Select masked subobject by clicking a row in SubObjects table,
   or click Undo to revert last coordinate placement
- Click either Finish to save changes into file or Reset to discard"""
    SUBOBJECT_TABLE_GROUP_STR = "Subobject Table"
    SUBOBJECT_ID_COLUMN_STR = "ID"
    SUBOBJECT_COORD_COLUMN_STR = "Coordinate"
    SUBOBJECT_COLOR_COLUMN_STR = "Color"
    OBJECT_LIST_COLUMNS = [SUBOBJECT_ID_COLUMN_STR, SUBOBJECT_COORD_COLUMN_STR, SUBOBJECT_COLOR_COLUMN_STR]

    def initGUI(self):
        self.twiHeadersList = []
        self.twiHash = {}
        self.setWindowTitle("Watershed Splitter")
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        instructionsButton = QtGui.QPushButton("See Instructions")
        instructionsButton.clicked.connect(self.instructionsButtonClicked)
        layout.addWidget(instructionsButton)
        configGroupBox = QtGui.QGroupBox("Configuration")
        layout.addWidget(configGroupBox)
        configLayout = QtGui.QVBoxLayout()
        configGroupBox.setLayout(configLayout)
        layout.addLayout(configLayout)
        dirBrowseLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(dirBrowseLayout)
        dirBrowseLayout.addWidget(QtGui.QLabel("Membrane Prediction"))
        self.dirEdit = QtGui.QLineEdit()
        dirBrowseLayout.addWidget(self.dirEdit)
        self.dirBrowseButton = QtGui.QPushButton("Browse...")
        self.dirBrowseButton.clicked.connect(self.dirBrowseButtonClicked)
        dirBrowseLayout.addWidget(self.dirBrowseButton)
        baseSizeLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(baseSizeLayout)
        baseSizeLayout.addWidget(QtGui.QLabel("Base SubObj ID"))
        self.baseSubObjIdEdit = QtGui.QLineEdit()
        baseSizeLayout.addWidget(self.baseSubObjIdEdit)
        baseSizeLayout.addWidget(QtGui.QLabel("Size"))
        self.workAreaSizeEdit = QtGui.QLineEdit()
        baseSizeLayout.addWidget(self.workAreaSizeEdit)
        opButtonsLayout = QtGui.QHBoxLayout()
        layout.addLayout(opButtonsLayout)
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

    def loadMembranePrediction(self, path, offset, size, addDistTransform):
        # Load membrane prediction
        membraneDataset = DatasetUtils.knossosDataset()
        membraneDataset.initialize_from_knossos_path(path)
        memPred = membraneDataset.from_cubes_to_matrix(size, offset, type='raw')

        # Get mem into shape
        memPred_inv = numpy.invert(((memPred > 0) * 255).astype(numpy.uint8))

        # Calculate distance transform
        distTransform = ndimage.distance_transform_edt(memPred_inv)

        # Return matrix
        return (1-addDistTransform)*memPred + addDistTransform*(255-distTransform)


    def calcNewMask(self, WS, ID):
        return WS == ID


    def waterseeds(self, newSeed, seedMatrix, mask, membranePred, newSeedID, oldWS, zoomFactor):
        # Translate seed list to matrix
        seedMatrix[tuple(newSeed)] = newSeedID
        # Calculate Watershed
        maskedWS = ndimage.zoom(watershed(membranePred, seedMatrix, None, None, ndimage.zoom(mask, 1/zoomFactor, order=0)), zoomFactor, order=0)
        oldWS[mask] = maskedWS[mask]
        return

    def finalizeTable(self, table):
        table.horizontalHeader().setStretchLastSection(True)
        self.resizeTable(table)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        return

    def initLogic(self):
        self.active = False
        self.zoomFactor = 1
        self.middleMouseSignal = signalRelay.Signal_EventModel_handleMouseReleaseMiddle
        self.middleMouseSignal.connect(self.handleMouseReleaseMiddle)
        return

    def uninitLogic(self):
        plugin_container.remove(self)
        self.middleMouseSignal.disconnect(self.handleMouseReleaseMiddle)
        return

    def closeEventYes(self,event):
        self.finishButtonClicked()
        event.accept()
        return
    
    def closeEventNo(self,event):
        self.resetButtonClicked()
        event.accept()
        return
    
    def closeEventAbort(self,event):
        event.ignore()
        return
    
    def closeEvent(self,event):
        if not self.active:
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

    def removeTableLastRow(self, table):
        table.removeRow(table.rowCount-1)
        return

    def instructionsButtonClicked(self):
        QtGui.QMessageBox.information(0, "Instructions", self.INSTRUCTION_TEXT_STR)
        return

    def dirBrowseButtonClicked(self):
        browse_dir = QtGui.QFileDialog.getExistingDirectory()
        if "" <> browse_dir:
            self.dirEdit.setText(browse_dir)
        return
    
    def subObjTableCellClicked(self, row, col):
        self.undoButton.enabled = False
        if self.masked_seed_row == row:
            return
        knossos.setPosition(self.coordList[row])
        self.masked_seed_row = row
        self.masked_seed_subObjId = self.baseSubObjId + self.masked_seed_row
        self.applyMask()
        return

    def str2tripint(self, s):
        tripint = map(int, re.findall(r"[\w']+", s))
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

    def applyMask(self):
        self.WS_mask = self.calcNewMask(self.WS,self.masked_seed_subObjId)
        self.WS_masked = self.newValMatrix(0)
        self.WS_masked[self.WS_mask] = self.WS[self.WS_mask]
        self.writeMatrix(self.WS_masked)
        return

    def matrixCopy(self, dst, src):
        dst[:,:,:] = src[:,:,:]
        return

    def handleMouseReleaseMiddle(self, eocd, clickedCoord, vpId, event):
        coord = list(clickedCoord.vector())
        if not self.active:
            if not self.begin(coord):
                return
        coord_arr = numpy.array(coord)
        coord_offset = (coord_arr - self.beginCoord_arr)/self.zoomFactor
        if self.WS_mask[tuple(coord_offset)] == False:
            QtGui.QMessageBox.information(0, "Error", "Click inside masked area!")
            return
        self.coordList.append(coord)
        self.last_seed += 1
        subObjId = self.baseSubObjId + self.last_seed
        self.matrixCopy(self.WS_prev,self.WS)
        self.waterseeds(coord_offset, self.seedMatrix, self.WS_mask, self.memPred, subObjId, self.WS, self.zoomFactor)
        self.matrixCopy(self.seedMatrix_prev,self.WS)
        self.addTableRow(self.subObjTable, [str(subObjId), coord, ""], atEnd = True)
        if self.last_seed == 0:
            self.subObjTable.selectRow(0)
            self.subObjTableCellClicked(0,0)
            return
        self.applyMask()
        self.undoButton.enabled = True
        return

    def undoButtonClicked(self):
        self.matrixCopy(self.WS,self.WS_prev)
        self.matrixCopy(self.seedMatrix,self.WS_prev)
        self.last_seed -= 1
        del self.coordList[-1]
        self.removeTableLastRow(self.subObjTable)
        self.applyMask()
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

    def resliceNotify(self, changeSetCoords):
        el = knossos.getCubeEdgeLength()
        for coord in changeSetCoords:
            knossos.oc_reslice_notify_all(list(numpy.array(coord)*el))
        return

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
        knossos.resetMovementArea()
        self.active = False
        self.clearTable(self.subObjTable)
        self.guiEnd()
        self.endMatrices()
        return
    
    def guiBegin(self):
        self.dirBrowseButton.enabled = False
        self.dirEdit.enabled = False
        self.baseSubObjIdEdit.enabled = False
        self.workAreaSizeEdit.enabled = False
        self.resetButton.enabled = True
        self.finishButton.enabled = True
        return

    def guiEnd(self):
        self.dirBrowseButton.enabled = True
        self.dirEdit.enabled = True
        self.baseSubObjIdEdit.enabled = True
        self.workAreaSizeEdit.enabled = True
        self.undoButton.enabled = False
        self.resetButton.enabled = False
        self.finishButton.enabled = False
        return

    def beginMatrices(self):
        self.orig = self.newValMatrix(0)
        self.readMatrix(self.orig)
        self.WS = self.newValMatrix(0)
        self.writeMatrix(self.WS)
        self.WS_prev = self.newValMatrix(0)
        self.WS_mask = self.calcNewMask(self.WS,0)
        self.seedMatrix = ndimage.zoom(self.newValMatrix(0), 1/self.zoomFactor, order=0)
        self.seedMatrix_prev = ndimage.zoom(self.newValMatrix(0), 1/self.zoomFactor, order=0)
        self.memPred = ndimage.zoom(self.loadMembranePrediction(self.validateDir(str(self.dirEdit.text)), self.beginCoord_arr, self.dims_arr, 0.1), 1/self.zoomFactor, order=0)
        return

    def endMatrices(self):
        del self.orig
        del self.WS
        del self.WS_mask
        del self.seedMatrix
        del self.memPred
        return

    def beginSeeds(self):
        self.baseSubObjId = long(str(self.baseSubObjIdEdit.text))
        self.coordList = []
        self.last_seed = -1
        self.masked_seed_row = -1
        self.masked_seed_subObjId = self.baseSubObjId + self.masked_seed_row
        return
    
    def begin(self, coord):
        retVal = True
        try:
            centerCoord_arr = numpy.array(coord)
            self.dims_arr = numpy.array(self.str2tripint(str(self.workAreaSizeEdit.text)))
            self.beginCoord_arr = centerCoord_arr - (self.dims_arr / 2)
            self.endCoord_arr = self.beginCoord_arr + self.dims_arr - 1
            knossos.setMovementArea(list(self.beginCoord_arr), list(self.endCoord_arr))
            self.beginMatrices()
            self.beginSeeds()
            self.guiBegin()
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
        knossos_global_mainwindow.saveAsSlot()
        self.commonEnd()
        return

    pass

plugin_container.append(watershedSplitter())
