from PythonQt import QtGui, Qt
import KnossosModule
import DatasetUtils, numpy, os, re, string, sys, time, traceback
from scipy import ndimage
DatasetUtils._set_noprint(True)

#KNOSSOS_PLUGIN Name BucketFiller
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Iteratively bucket fill a segmentation object based on a pre-calculated membrane prediction

class bucketFiller(QtGui.QWidget):
    INSTRUCTION_TEXT_STR = """Fill configuration:
- Pick membrane prediction dataset by browsing to directory of knossos.conf
- Base subobject ID for subobjects to be created
- Size of work area,  as an x,y,z blank-separated tuple
  Work area should not exceed supercube size

Operation:
- For each cell, enter a subObject Id. Then iteratively:
-- Move to a place inside the cell (stay in mag1), and wait for the loader to finish
-- Click Fill to bucket fill
"""
    def initGUI(self):
        self.twiHeadersList = []
        self.twiHash = {}
        self.setWindowTitle("Bucket Filler")
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
        memPredLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(memPredLayout)
        memPredLayout.addWidget(QtGui.QLabel("Membrane Prediction"))
        self.dirEdit = QtGui.QLineEdit()
        memPredLayout.addWidget(self.dirEdit)
        self.dirBrowseButton = QtGui.QPushButton("Browse...")
        self.dirBrowseButton.clicked.connect(self.dirBrowseButtonClicked)
        memPredLayout.addWidget(self.dirBrowseButton)
        subObjSizeLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(subObjSizeLayout)
        subObjSizeLayout.addWidget(QtGui.QLabel("SubObj ID"))
        self.subObjIdEdit = QtGui.QLineEdit()
        subObjSizeLayout.addWidget(self.subObjIdEdit)
        subObjSizeLayout.addWidget(QtGui.QLabel("Size"))
        self.workAreaSizeEdit = QtGui.QLineEdit()
        subObjSizeLayout.addWidget(self.workAreaSizeEdit)
        itersThresholdLayout = QtGui.QHBoxLayout()
        configLayout.addLayout(itersThresholdLayout)
        itersThresholdLayout.addWidget(QtGui.QLabel("Iterations"))
        self.itersEdit = QtGui.QLineEdit()
        itersThresholdLayout.addWidget(self.itersEdit)
        itersThresholdLayout.addWidget(QtGui.QLabel("Threshold"))
        self.thresholdEdit = QtGui.QLineEdit()
        itersThresholdLayout.addWidget(self.thresholdEdit)
        fillUndoLayout = QtGui.QHBoxLayout()
        layout.addLayout(fillUndoLayout)
        self.fillButton = QtGui.QPushButton("Fill")
        self.fillButton.clicked.connect(self.fillButtonClicked)
        fillUndoLayout.addWidget(self.fillButton)
        self.UndoButton = QtGui.QPushButton("Undo")
        self.UndoButton.clicked.connect(self.UndoButtonClicked)
        fillUndoLayout.addWidget(self.UndoButton)
        # Show
        self.setWindowFlags(Qt.Qt.Window)
        self.show()
        return

    def __init__(self, parent=KnossosModule.knossos_global_mainwindow):
        super(main_class, self).__init__(parent, Qt.Qt.WA_DeleteOnClose)
        KnossosModule.plugin_container[main_class.__name__] = self
        self.initGUI()
        self.initLogic()
        return

    def initLogic(self):
        KnossosModule.signalRelay.Signal_EventModel_handleMouseReleaseMiddle.connect(self.handleMouseReleaseMiddle)
        self.pos_arr = numpy.array(KnossosModule.knossos.getPosition())
        return
    
    def handleMouseReleaseMiddle(self, eocd, coord, event):
        self.pos_arr = numpy.array(coord.vector())
        KnossosModule.knossos.setPosition(coord.vector())
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
        tripint = map(int, re.findall(r"[\w']+", s))
        assert(len(tripint) == 3)
        return tripint

    def validateDir(self, s):
        if s[-1] <> "/":
            s += "/"
        assert(os.path.isdir(s))
        return s

    def npDataPtr(self, matrix):
        return matrix.__array_interface__["data"][0]

    def writeMatrix(self, matrix):
        return KnossosModule.knossos.processRegionByStridedBufProxy(self.begin_arr, self.size_arr, self.npDataPtr(matrix), matrix.strides, True, True)

    def readMatrix(self, matrix):
        return KnossosModule.knossos.processRegionByStridedBufProxy(self.begin_arr, self.size_arr, self.npDataPtr(matrix), matrix.strides, False, False)

    def fillButtonClicked(self):
        path = self.validateDir(str(self.dirEdit.text))
        self.size_arr = numpy.array(self.str2tripint(str(self.workAreaSizeEdit.text)))
        subObjId = int(str(self.subObjIdEdit.text))
        iters = int(str(self.itersEdit.text))
        threshold = int(str(self.thresholdEdit.text))
        pos_off_arr = self.size_arr/2
        self.begin_arr = self.pos_arr - pos_off_arr
        
        memPredDataset = DatasetUtils.knossosDataset()
        memPredDataset.initialize_from_knossos_path(path)
        memPred = memPredDataset.from_cubes_to_matrix(self.size_arr, self.begin_arr, type='raw')
	
        dil = ndimage.morphology.binary_dilation(memPred > threshold, iterations = iters)
        del memPred
        if dil[tuple(pos_off_arr)]:
            QtGui.QMessageBox.information(0, "Error", "Dilation error")
            return
        all_labels, num = ndimage.measurements.label(numpy.invert(dil))
        del dil
        requested_label = all_labels[tuple(pos_off_arr)]
        seg = ndimage.morphology.binary_dilation((all_labels == requested_label), iterations = iters + 1)
        del all_labels
        self.inputMatrix = numpy.ndarray(shape=self.size_arr,dtype="uint64")
        self.inputMatrix.fill(0)
        self.readMatrix(self.inputMatrix)
        outputMatrix = numpy.ndarray(shape=self.size_arr,dtype="uint64")
        outputMatrix[:,:,:] = self.inputMatrix[:,:,:]
        outputMatrix[seg] = subObjId
        self.writeMatrix(outputMatrix)
        return
    
    def UndoButtonClicked(self):
        self.writeMatrix(self.inputMatrix)
        return
    
    pass

main_class = bucketFiller
main_class()
