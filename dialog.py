from PythonQt import QtGui

#KNOSSOS_PLUGIN Name Dialog
#KNOSSOS_PLUGIN	Version	1
#KNOSSOS_PLUGIN Description Dialog and button
#KNOSSOS_PLUGIN Another_Field	Another field content

class dialogPlugin(QtGui.QDialog):
    def __init__(self, parent=None):
        super(dialogPlugin, self).__init__(parent)
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        pushMeButton = QtGui.QPushButton("Push Me")
        layout.addWidget(pushMeButton)
        pushMeButton.clicked.connect(self.pushMeButtonClicked)
        self.show()
        return
    
    def pushMeButtonClicked(self):
        QtGui.QMessageBox.information(0, "Push", "Me", QtGui.QMessageBox.Ok)
        return
    
    pass

plugin_container.append(dialogPlugin())
