from PythonQt import QtGui, Qt
import KnossosModule

#KNOSSOS_PLUGIN	Version	1
#KNOSSOS_PLUGIN	Description	Dialog and button
#KNOSSOS_PLUGIN Another_Field	Another field content

class main_class(QtGui.QDialog):
    def __init__(self, parent=KnossosModule.knossos_global_mainwindow):
        super(main_class, self).__init__(parent)
        exec(KnossosModule.scripting.getInstanceInContainerStr(__name__) + " = self")
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        pushMeButton = QtGui.QPushButton("Push Me")
        layout.addWidget(pushMeButton)
        pushMeButton.clicked.connect(self.pushMeButtonClicked)
        self.setWindowFlags(Qt.Qt.Window)
        self.show()
        return

    def pushMeButtonClicked(self):
        QtGui.QMessageBox.information(0, "Push", "Me", QtGui.QMessageBox.Ok)
        return
    
    pass
