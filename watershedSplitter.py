from PythonQt import QtGui, Qt
import numpy, traceback, re, time
from scipy import ndimage
from skimage.morphology import watershed

#KNOSSOS_PLUGIN Name WatershedSplitter
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Splits a misannotated cell into constituent cells using a watershed algorithm on a background distance transform, supplemented by manual border seeding

class watershedSplitter(QtGui.QWidget):
    INSTRUCTION_TEXT_STR = """
Concept:

Watershed Splitter is a knossos annotation plugin that facilitates the spliting of a misannotated single segmentation object comprised of several cells into single cell objects - by defining a border between them. Each cell is considered a "basin", and one or more "seeds" are placed at the "bottom level" of the basin. In addition, barriers between cells is delineated by groups of points. Together with the background surrounding the misannotated cell, the inner-most positions of each constituent cell are calculated using a distance transform on the background and the barriers. These positions and the gradients towards them are approximations for the topography of the basins. The basin seeds and topography are fed to a "watershed" algorithm. There, all basins are "flooded with water", until waters of different basins meet. Each flooded basin is labelled as a distinct cell.

Configuration:
- Size - (voxel) size of work area as x,y,z blank-separated tuples. In case a work area is already
  defined upon beginning, this size serves as a cap to restrict working on a larger size
- Marker Radius - radius of marker for visualizing seed location
- Base ID - IDs of created subobjects start growing from this number

Operation:
- Click begin. If a work area was not defined beforehand, it would be defined now, so movement is confined to it
- Press the middle button (or wheel) of the mouse on the misannotated cell you wish to split. This would mask off
  all other cells
- To seed basins, middle-click them. This would immediately calculate the watershed and update the viewport display
- To place several seeds for a basin, precede the final middle-click with Shift+middle-click on other seed coordinates
- Use Ctrl+middle-click to mark barriers. As before, precede this with Shift+middle-click to mark several coordinates
  prior to the final Ctrl+middle-click
- The table lists basins in normal script and barriers in italic
- To delete a basin or a barrier, select in the table and press the Delete key
- Press the Reset button at any time to cancel all work done
- Press Finish to write the split cells back to knossos
"""
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
        def __init__(self, delF, parent=None):
            QtGui.QTableWidget.__init__(self,parent)
            self._delF = delF
            return

        def keyPressEvent(self, event):
            if event.key() == Qt.Qt.Key_Delete:
                self._delF()
            return QtGui.QTableWidget.keyPressEvent(self,event)
        pass

    def initGUI(self):
        self.setWindowTitle("Watershed Splitter")
        widgetLayout = QtGui.QVBoxLayout()
        self.setLayout(widgetLayout)
        instructionsButton = QtGui.QPushButton("See Instructions")
        instructionsButton.clicked.connect(self.instructionsButtonClicked)
        widgetLayout.addWidget(instructionsButton)
        configLayout = QtGui.QHBoxLayout()
        widgetLayout.addLayout(configLayout)
        configLayout.addWidget(QtGui.QLabel("Marker Radius"))
        self.markerRadiusEdit = QtGui.QLineEdit()
        configLayout.addWidget(self.markerRadiusEdit)
        configLayout.addWidget(QtGui.QLabel("Base ID"))
        self.baseSubObjIdEdit = QtGui.QLineEdit()
        configLayout.addWidget(self.baseSubObjIdEdit)
        configLayout.addWidget(QtGui.QLabel("Size"))
        self.workAreaSizeEdit = QtGui.QLineEdit()
        configLayout.addWidget(self.workAreaSizeEdit)
        opButtonsLayout = QtGui.QHBoxLayout()
        widgetLayout.addLayout(opButtonsLayout)
        self.beginButton = QtGui.QPushButton("Begin")
        self.beginButton.clicked.connect(self.beginButtonClicked)
        opButtonsLayout.addWidget(self.beginButton)
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
        widgetLayout.addLayout(subObjTableLayout)
        self.subObjTableGroupBox.setLayout(subObjTableLayout)
        self.subObjTable = self.MyTableWidget(self.subObjTableDel)
        subObjTableWidget = QtGui.QWidget()
        subObjTableLayout.addWidget(subObjTableWidget)
        subObjTableLayout = QtGui.QVBoxLayout()
        subObjTableWidget.setLayout(subObjTableLayout)
        subObjTableLayout.addWidget(self.subObjTable)
        self.setTableHeaders(self.subObjTable, self.OBJECT_LIST_COLUMNS)
        self.finalizeTable(self.subObjTable)
        # Instructions
        self.instructionsWidget = QtGui.QWidget()
        self.instructionsWidget.setWindowTitle("Watershed Plugin Instructions")
        instructionsLayout = QtGui.QVBoxLayout()
        self.instructionsWidget.setLayout(instructionsLayout)
        self.instructionsTextEdit = QtGui.QTextEdit()
        self.instructionsTextEdit.setPlainText(self.INSTRUCTION_TEXT_STR)
        self.instructionsTextEdit.setAlignment(Qt.Qt.AlignJustify)
        self.instructionsTextEdit.setReadOnly(True)
        instructionsLayout.addWidget(self.instructionsTextEdit)
        self.instructionsWidget.resize(600,400)
        # Invisibles
        self.widgetWidthEdit = QtGui.QLineEdit()
        self.widgetHeightEdit = QtGui.QLineEdit()
        self.curFont = QtGui.QFont()
        # Show
        self.setWindowFlags(Qt.Qt.Window)
        self.show()
        Qt.QApplication.processEvents()
        self.resize(0,0)
        return

    def __init__(self, parent=knossos_global_mainwindow):
        super(watershedSplitter, self).__init__(parent, Qt.Qt.WA_DeleteOnClose)
        self.initGUI()
        self.initLogic()
        return

    def finalizeTable(self, table):
        table.horizontalHeader().setStretchLastSection(True)
        self.resizeTable(table)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        return

    def applyGuiConfig(self):
        width = int(self.widgetWidthEdit.text)
        height = int(self.widgetHeightEdit.text)
        self.resize(width,height)
        return

    def generateGuiConfig(self):
        self.widgetWidthEdit.text = str(self.size.width())
        self.widgetHeightEdit.text = str(self.size.height())
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
        self.settings = [(self.baseSubObjIdEdit,"BASE_SUB_OBJ_ID","10000000"), \
                        (self.workAreaSizeEdit,"WORK_AREA_SIZE",str(tuple([knossos.getCubeEdgeLength()*2]*3))), \
                        (self.markerRadiusEdit,"MARKER_RADIUS","1"), \
                       (self.widgetWidthEdit,"WIDGET_WIDTH", "0"), \
                       (self.widgetHeightEdit,"WIDGET_HEIGHT", "0")]
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

    def clearTable(self):
        table = self.subObjTable
        table.clearContents()
        table.setRowCount(0)
        return

    def resizeTable(self, table):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        return

    def addTableRow(self, table, columnTexts, isSlack):
        rowIndex = 0
        table.insertRow(rowIndex)
        for i in xrange(len(columnTexts)):
            twi = QtGui.QTableWidgetItem(columnTexts[i])
            twi.setFlags(twi.flags() & (~Qt.Qt.ItemIsEditable))
            self.curFont.setItalic(isSlack)
            twi.setFont(self.curFont)
            table.setItem(rowIndex, i, twi)
        self.resizeTable(table)
        return

    def instructionsButtonClicked(self):
        self.instructionsWidget.show()
        return

    def str2tripint(self, s):
        tripint = map(long, re.findall(r"[\w']+", s))
        assert(len(tripint) == 3)
        return tripint

    def nextId(self):
        return max(self.mapIdToCoord.keys() + [self.baseSubObjId - 1]) + 1

    def IdFromRow(self, row):
        table = self.subObjTable
        if (row > table.rowCount) or (row < 0):
            return self.invalidId
        return long(table.item(row,0).text())

    def RowFromId(self, Id):
        table = self.subObjTable
        for row in xrange(table.rowCount):
            if self.IdFromRow(row) == Id:
                return row
        return self.invalidRow

    def getTableSelectedRow(self):
        table = self.subObjTable
        return [x.row() for x in table.selectionModel().selectedRows()]
    
    def TreeIdById(self,Id):
        if Id in self.mapIdToTreeId:
            return self.mapIdToTreeId[Id]
        treeId = skeleton.findAvailableTreeID()
        skeleton.add_tree(treeId)
        self.mapIdToTreeId[Id] = treeId
        return treeId

    def addMoreCoords(self, coord, coord_offset, vpId):
        self.moreCoords.append((coord,coord_offset,vpId))
        self.addNode(coord, self.TreeIdById(self.nextId()), vpId)
        return

    def addNode(self,coord,treeId,vpId):
        nodeId = skeleton.findAvailableNodeID()
        skeleton.add_node(*((nodeId,)+coord+(treeId,self.markerRadius,vpId,)))
        return nodeId

    def displayCoord(self,coord):
        return tuple(numpy.array(coord)+1)

    def matrixDelId(self,Id,isSlack):
        for coordTuple in self.mapIdToSeedTuples[Id]:
            coord_offset = coordTuple[1]
            if isSlack:
                self.memPredPad[tuple(numpy.array(coord_offset)+self.pad)] = True
            else:
                self.seedMatrix[coord_offset] = 0
        del self.mapIdToSeedTuples[Id]
        return

    def matrixSetId(self,coordTuples,Id,isSlack):
        for coordTuple in coordTuples:
            coord_offset = coordTuple[1]
            if isSlack:
                self.memPredPad[tuple(numpy.array(coord_offset)+self.pad)] = False
            else:
                self.seedMatrix[coord_offset] = Id
        self.mapIdToSeedTuples[Id] = coordTuples
        return

    def addSeed(self, coord, coord_offset, vpId, isSlack=False):
        Id = self.nextId()
        coordTuples = [(coord, coord_offset, vpId)] + self.moreCoords
        self.matrixSetId(coordTuples,Id,isSlack)
        self.mapIdToSlack[Id] = isSlack
        self.mapIdToCoord[Id] = coord
        self.mapIdToNodeId[Id] = self.addNode(coord,self.TreeIdById(Id),vpId)
        self.mapIdToMoreCoords[Id] = [curCoord[0] for curCoord in self.moreCoords]
        self.refreshTable()
        self.calcWS()
        self.moreCoords = []
        self.updateFinishButton()
        return

    def refreshTable(self):
        table = self.subObjTable
        self.clearTable()
        for (Id,coord) in self.getSortedMapItems():
            self.addTableRow(table, [str(Id), str(self.displayCoord(coord)), str(map(self.displayCoord,self.mapIdToMoreCoords[Id]))], self.mapIdToSlack[Id])
        return

    def updateFinishButton(self):
        self.finishButton.enabled = len(self.nonSlacks()) > 1
        return
    
    def removeSeeds(self,Ids):
        if len(Ids) == 0:
            return
        for Id in Ids:
            self.matrixDelId(Id,self.mapIdToSlack[Id])
            del self.mapIdToCoord[Id]
            skeleton.delete_tree(self.mapIdToTreeId[Id])
            del self.mapIdToTreeId[Id]
            del self.mapIdToNodeId[Id]
            del self.mapIdToSlack[Id]
        self.refreshTable()
        self.calcWS()
        self.updateFinishButton()
        return

    def subObjTableDel(self):
        rows = self.getTableSelectedRow()
        if len(rows) == 0:
            return
        self.removeSeeds([self.IdFromRow(row) for row in rows])
        return

    def getSortedMapItems(self):
        IdCoordTuples = self.mapIdToCoord.items()
        IdCoordTuples.sort()
        return IdCoordTuples

    def waitForLoader(self):
        busyScope = self.BusyCursorScope()
        while knossos_global_loader.getRefCount() > 0:
            Qt.QApplication.processEvents()
            time.sleep(0)
        return

    def coordOffset(self,coord):
        return tuple(numpy.array(coord) - self.beginCoord_arr)

    def nonSlacks(self):
        h = self.mapIdToSlack
        return filter(lambda x: not h[x], h)

    def calcWS(self):
        busyScope = self.BusyCursorScope()
        nonSlackIds = self.nonSlacks()
        nonSlackCount = len(nonSlackIds)
        if nonSlackCount == 0:
            self.WS_masked[self.WS_mask] = self.curObjId
        elif nonSlackCount == 1:
            self.WS_masked[self.WS_mask] = nonSlackIds[0]
        else:
            self.distMemPred = -ndimage.distance_transform_edt(self.memPredPad)
            pad = self.pad
            self.distMemPred = self.distMemPred[pad:-pad,pad:-pad,pad:-pad]
            self.distMemPred = self.scaleMatrix(self.distMemPred,0,1)
            seededDist = self.distMemPred-((self.seedMatrix > 0)*1.0)
            ws = watershed(seededDist, self.seedMatrix, None, None, self.WS_mask)
            self.WS_masked[self.WS_mask] = ws[self.WS_mask]
        self.writeMatrix(self.WS_masked)
        return

    def setObjId(self,Id):
        busyScope = self.BusyCursorScope()
        self.curObjId = Id
        self.WS_mask = self.orig == self.curObjId
        self.WS_masked[self.WS_mask] = self.orig[self.WS_mask]
        pad = self.pad
        self.memPredPad = numpy.pad(self.WS_mask,((pad,pad),)*3,'constant',constant_values=((False,False),)*3)
        self.writeMatrix(self.WS_masked)
        return
    
    def handleMouseReleaseMiddle(self, eocd, clickedCoord, vpId, event):
        if not self.active:
            return
        coord = tuple(clickedCoord.vector())
        coord_offset = self.coordOffset(coord)
        mods = event.modifiers()
        if self.curObjId == self.invalidId:
            if mods == 0:
                self.setObjId(self.orig[coord_offset])
            else:
                QtGui.QMessageBox.information(0, "Error", "First select object!")
            return
        if self.WS_mask[coord_offset] == False:
            QtGui.QMessageBox.information(0, "Error", "Click inside mask!")
            return
        if mods == 0:
            t = time.time()
            self.addSeed(coord,coord_offset,vpId)
        elif mods == Qt.Qt.ShiftModifier:
            self.addMoreCoords(coord,coord_offset,vpId)
        elif mods == Qt.Qt.ControlModifier:
            self.addSeed(coord,coord_offset,vpId,isSlack=True)
        return

    def npDataPtr(self, matrix):
        return matrix.__array_interface__["data"][0]

    def accessMatrix(self, matrix, isWrite):
        self.waitForLoader()
        return knossos.processRegionByStridedBufProxy(list(self.beginCoord_arr), list(self.dims_arr), self.npDataPtr(matrix), matrix.strides, isWrite, True)

    def writeMatrix(self, matrix):
        self.accessMatrix(matrix, True)
        return

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
        self.active = False
        self.clearTable()
        for treeId in self.mapIdToTreeId.values():
            skeleton.delete_tree(treeId)
        self.guiEnd()
        self.endMatrices()
        if not self.confined:
            knossos.resetMovementArea()
        return
    
    def guiBegin(self):
        self.beginButton.enabled = False
        self.resetButton.enabled = True
        return

    def guiEnd(self):
        self.beginButton.enabled = True
        self.resetButton.enabled = False
        self.finishButton.enabled = False
        return

    def scaleMatrix(self,m,minVal,maxVal):
        curMinVal = m.min()
        curRange = m.max() - curMinVal
        newRange = maxVal - minVal
        return ((m - curMinVal)*(newRange/curRange))+minVal

    def beginMatrices(self):
        self.orig = self.newMatrix(dims=self.dims_arr)
        self.readMatrix(self.orig)
        self.seedMatrix = self.newValMatrix(0)
        self.WS_masked = self.newValMatrix(0)
        self.distMemPred = self.newValMatrix(0)
        return

    def endMatrices(self):
        del self.orig
        del self.seedMatrix
        del self.WS_masked
        del self.distMemPred
        if self.curObjId == self.invalidId:
            return
        del self.WS_mask
        del self.memPredPad
        return

    def finalizeSubObjs(self):
        nonSlackIds = self.nonSlacks()
        firstId = nonSlackIds[0]
        self.WS_masked[self.WS_masked == firstId] = self.curObjId
        nonSlackIds[0] = self.curObjId
        self.mapIdToCoord[self.curObjId] = self.mapIdToCoord[firstId]
        for Id in nonSlackIds:
            coord = self.mapIdToCoord[Id]
            segmentation.subobjectFromId(Id, coord)
            objIndex = segmentation.largestObjectContainingSubobject(Id,(0,0,0))
            segmentation.changeComment(objIndex,"WatershedSplitter")
        return

    def beginSeeds(self):
        self.curObjId = self.invalidId
        self.mapIdToCoord = {}
        self.mapIdToTreeId = {}
        self.moreCoords = []
        self.mapIdToMoreCoords = {}
        self.mapIdToNodeId = {}
        self.mapIdToSlack = {}
        self.mapIdToTodo = {}
        self.mapIdToSeedTuples = {}
        return

    def isSizeSmaller(self,smallSize,refSize):
        return not (True in (smallSize > refSize))
    
    def beginButtonClicked(self):
        retVal = True
        try:
            self.invalidId = 0L
            self.invalidRow = -1
            self.pad = 1
            # parse edits
            self.dims_arr = numpy.array(self.str2tripint(str(self.workAreaSizeEdit.text)))
            self.baseSubObjId = long(str(self.baseSubObjIdEdit.text))
            self.markerRadius = int(self.markerRadiusEdit.text)
            movementArea_arr = numpy.array(knossos.getMovementArea())
            self.movementAreaBegin_arr, self.movementAreaEnd_arr = movementArea_arr[:3], movementArea_arr[3:]+1
            self.movementAreaSize_arr = self.movementAreaEnd_arr - self.movementAreaBegin_arr
            if self.isSizeSmaller(self.movementAreaSize_arr, self.dims_arr):
                self.confined = True
                self.dims_arr = self.movementAreaSize_arr
                self.beginCoord_arr = self.movementAreaBegin_arr
                self.endCoord_arr = self.movementAreaEnd_arr
            else:
                self.confined = False
                self.middleCoord_arr = numpy.array(knossos.getPosition())
                self.beginCoord_arr = self.middleCoord_arr - (self.dims_arr/2)
                self.endCoord_arr = self.beginCoord_arr + self.dims_arr
                knossos.setMovementArea(list(self.beginCoord_arr), list(self.endCoord_arr))
            self.beginSeeds()
            self.beginMatrices()
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
        self.finalizeSubObjs()
        self.orig[self.WS_mask] = self.WS_masked[self.WS_mask]
        self.writeMatrix(self.orig)
        self.commonEnd()
        return

plugin_container.append(watershedSplitter())
