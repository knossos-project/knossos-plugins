from PythonQt import QtGui, Qt
import KnossosModule

#KNOSSOS_PLUGIN Name Dialog
#KNOSSOS_PLUGIN	Version	1
#KNOSSOS_PLUGIN Description Dialog and button
#KNOSSOS_PLUGIN Another_Field	Another field content

class dialog(QtGui.QDialog):
    def __init__(self, parent=KnossosModule.knossos_global_mainwindow):
        super(main_class, self).__init__(parent, Qt.Qt.WA_DeleteOnClose)
        KnossosModule.plugin_container[main_class.__name__] = self
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

main_class = dialog
main_class()
