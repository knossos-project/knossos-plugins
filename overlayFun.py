from PythonQt import QtGui, Qt
from random import randint
from math import sqrt
import numpy

#KNOSSOS_PLUGIN Name OverlayFun
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Constantly paints and unpaints radial overlay circles at position selected by mouse middle-click

class overlayPainter(QtGui.QWidget):
    TIMER_BUTTON_STRS = ["Paused", "Works"]
    def __init__(self, parent=None):
        # Logic
        self.newRadius = self.radius = 20
        self.newPos = self.position = knossos.getPosition()
        self.coords = {}
        self.orig = self.emptyData()
        self.ours = self.emptyData()
        # GUI
        super(overlayPainter, self).__init__(parent)
        self.setWindowTitle("Overlay Fun")
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        self.hoverPositionLabel = QtGui.QLabel()
        layout.addWidget(self.hoverPositionLabel)
        layout.addWidget(QtGui.QLabel("Draw Position"))
        self.positionLabel = QtGui.QLabel()
        layout.addWidget(self.positionLabel)
        layout.addWidget(QtGui.QLabel("Radius"))
        self.radiusEdit = QtGui.QLineEdit(str(self.radius))
        self.radiusEdit.editingFinished.connect(self.setRadiusSlot)
        layout.addWidget(self.radiusEdit)
        layout.addWidget(QtGui.QLabel("Interval"))
        self.interval = QtGui.QLineEdit("100")
        layout.addWidget(self.interval)
        self.interval.editingFinished.connect(self.setIntervalSlot)
        self.timerButton = QtGui.QPushButton()
        layout.addWidget(self.timerButton)
        self.timer = Qt.QTimer()
        self.setIntervalSlot()
        self.timer.timeout.connect(self.timerSlot)
        self.timerButton.setCheckable(True)
        self.timerButton.setChecked(False)
        self.timerButton.toggled.connect(self.timerButtonToggledSlot)
        self.timerButtonToggledSlot()
        # Connect knossos signals
        signalRelay.Signal_EventModel_handleMouseReleaseMiddle.connect(self.knossosMiddleButtonRelease)
        signalRelay.Signal_EventModel_handleMouseHover.connect(self.knossosMouseHover)
        # Kick-off
        self.show()
        self.startPosition()
        return

    def emptyData(self):
        return numpy.ndarray((self.radius*2+1,)*3,numpy.int64,)

    def posOffset(self, pos):
        return tuple([(self.radius + pos[i] - self.position[i]) for i in xrange(len(pos))])

    def genCoords(self):
        x, y, z = self.position
        r = self.radius + 1
        self.coords = {}
        for cx in xrange(-r,r+1):
            for cy in xrange(-r,r+1):
                for cz in xrange(-r,r+1):
                    curR = int(sqrt(cx*cx + cy*cy + cz*cz))
                    if curR < r:
                        self.coords.setdefault(curR,[]).append((x+cx, y+cy, z+cz))
        return

    def coord2pos(self, coord):
        return (coord.x(), coord.y(), coord.z())
    
    def cleanPosition(self):
        for curR in self.coords:
            for pos in self.coords[curR]:
                knossos.writeOverlayVoxel(*(pos + (self.orig[self.posOffset(pos)],)))
        knossos_global_viewer.oc_reslice_notify()
        return

    def stopTimer(self):
        self.timer.stop()
        return

    def startTimer(self):
        self.timer.start(int(self.interval.text))
        return

    def saveOrig(self):
        self.orig = self.emptyData()
        for curR in self.coords:
            for pos in self.coords[curR]:
                self.orig[self.posOffset(pos)] = knossos.readOverlayVoxel(*pos)
        return

    def genOurs(self):
        self.ours = self.emptyData()
        seed = abs(self.position.__hash__())
        for r in self.coords:
            for pos in self.coords[r]:
                self.ours[self.posOffset(pos)] = abs((seed + r).__hash__())
        return
    
    def startPosition(self):
        self.genCoords()
        self.saveOrig()
        self.genOurs() 
        self.R = 0
        self.expand = True
        self.data = self.ours
        self.positionLabel.text = "%d,%d,%d" % self.position
        return

    def restart(self):
        self.cleanPosition()
        self.position = self.newPos
        self.radius = self.newRadius
        self.startPosition()
        return

    def knossosMiddleButtonRelease(self, eocd, coord, vpId, event):
        self.newPos = self.coord2pos(coord)
        self.newRadius = self.radius
        self.restart()
        return

    def knossosMouseHover(self, eocd, coord, subObjId, vpId, event):
        self.hoverPositionLabel.text = "subObjId @ %d,%d,%d = %d" % (self.coord2pos(coord) + (subObjId,))
        return

    def setRadiusSlot(self):
        self.newRadius = int(self.radiusEdit.text)
        self.newPos = self.position
        self.restart()
        return

    def timerButtonToggledSlot(self):
        isChecked = self.timerButton.isChecked()
        self.timerButton.text = self.TIMER_BUTTON_STRS[int(isChecked)]
        if isChecked:
            self.startPosition()
            self.startTimer()
        else:
            self.stopTimer()
            self.cleanPosition()
        return

    def setIntervalSlot(self):
        self.stopTimer()
        self.timer.setInterval(int(self.interval.text))
        self.startTimer()
        return

    def updateR(self):
        if self.expand:
            self.R += 1
            if self.R > self.radius:
                self.expand = False
                self.R = self.radius
                self.data = self.orig
        else:
            self.R -= 1
            if self.R == -1:
                self.expand = True
                self.R = 0
                self.data = self.ours
        return

    def writeOverlay(self):
        for pos in self.coords[self.R]:
            knossos.writeOverlayVoxel(*(pos + (self.data[self.posOffset(pos)],)))
        knossos_global_viewer.oc_reslice_notify()
        return
    
    def timerSlot(self):
        self.writeOverlay()
        self.updateR()
        return
    
    pass

op = overlayPainter()
