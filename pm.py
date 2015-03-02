from PythonQt import QtGui, Qt

class pluginMgr:
    def __init__(self):
        # General
        self.widget = QtGui.QWidget()
        self.widget.setWindowTitle("Plugin Manager")
        layout = QtGui.QVBoxLayout()
        self.widget.setLayout(layout)
        # Local Dir 
        localDirGroupBox = QtGui.QGroupBox("Local Repository")
        layout.addWidget(localDirGroupBox)
        localDirLayout = QtGui.QVBoxLayout()
        localDirGroupBox.setLayout(localDirLayout)
        localDirSelectLayout = QtGui.QHBoxLayout()
        localDirLayout.addLayout(localDirSelectLayout)
        localDirLabel = QtGui.QLabel("Path")
        localDirSelectLayout.addWidget(localDirLabel)
        self.localDirEdit = QtGui.QLineEdit()
        localDirSelectLayout.addWidget(self.localDirEdit)
        localDirBrowseButton = QtGui.QPushButton("Browse...")
        localDirBrowseButton.clicked.connect(self.localDirBrowseButtonClicked)
        localDirSelectLayout.addWidget(localDirBrowseButton)
        localDirDefaultButton = QtGui.QPushButton("Default")
        localDirDefaultButton.clicked.connect(self.localDirDefaultButtonClicked)
        localDirSelectLayout.addWidget(localDirDefaultButton)
        localDirListButton = QtGui.QPushButton("List")
        localDirListButton.clicked.connect(self.localDirListButtonClicked)
        localDirSelectLayout.addWidget(localDirListButton)
        localDirListLayout = QtGui.QGridLayout()
        localDirLayout.addLayout(localDirListLayout)
        localDirListLayout.addWidget(QtGui.QLabel("Plugins"), 0, 0)
        localDirListLayout.addWidget(QtGui.QLabel("MetaData"), 0, 1)
        self.localDirPluginTable = QtGui.QTableWidget()
        localDirListLayout.addWidget(self.localDirPluginTable, 1, 0)
        self.localDirMetaDataTable = QtGui.QTableWidget()
        localDirListLayout.addWidget(self.localDirMetaDataTable, 1, 1)
        # Sync
        remoteToLocalButton = QtGui.QPushButton("Remote->Local")
        remoteToLocalButton.clicked.connect(self.remoteToLocalButtonClicked)
        layout.addWidget(remoteToLocalButton)
        # Repository
        repoGroupBox = QtGui.QGroupBox("Remote Repository")
        repoLayout = QtGui.QVBoxLayout()
        repoGroupBox.setLayout(repoLayout)
        layout.addWidget(repoGroupBox)
        repoSelectLayout = QtGui.QHBoxLayout()
        repoLayout.addLayout(repoSelectLayout)
        repoSelectLayout.addWidget(QtGui.QLabel("URL"))
        self.repoUrlEdit = QtGui.QLineEdit()
        repoSelectLayout.addWidget(self.repoUrlEdit)
        repoDefaultButton = QtGui.QPushButton("Default")
        repoDefaultButton.clicked.connect(self.repoDefaultButtonClicked)
        repoSelectLayout.addWidget(repoDefaultButton)
        repoListButton = QtGui.QPushButton("List")
        repoListButton.clicked.connect(self.repoListButtonClicked)
        repoSelectLayout.addWidget(repoListButton)
        repoListLayout = QtGui.QGridLayout()
        repoLayout.addLayout(repoListLayout)
        repoListLayout.addWidget(QtGui.QLabel("Plugins"), 0, 0)
        repoListLayout.addWidget(QtGui.QLabel("MetaData"), 0, 1)
        self.repoPluginTable = QtGui.QTableWidget()
        repoListLayout.addWidget(self.repoPluginTable, 1, 0)
        self.repoMetaDataTable = QtGui.QTableWidget()
        repoListLayout.addWidget(self.repoMetaDataTable, 1, 1)
        # General
        self.widget.show()
        self.localDirDefaultButtonClicked()
        return

    def localDirBrowseButtonClicked(self):
        browse_dir = QtGui.QFileDialog.getExistingDirectory()
        if "" <> browse_dir:
            self.localDirEdit.setText(browse_dir)
        return
    
    def localDirDefaultButtonClicked(self):
        defaultDir = Qt.QDir.homePath() + "/" + "knos_plg"
        exists = Qt.QDir(defaultDir).exists()
        if not exists:
            mb = QtGui.QMessageBox
            if mb.Ok == mb.question(0, "Default Directory", "Default directory does not exists. Create?", mb.Ok | mb.Cancel):
                Qt.QDir().mkpath(defaultDir)
                exists = True
        if exists:
            self.localDirEdit.setText(defaultDir)
        return
    
    def localDirListButtonClicked(self):
        # TODO
        return

    def repoDefaultButtonClicked(self):
        # TODO
        return

    def repoListButtonClicked(self):
        # TODO
        return
    
    def remoteToLocalButtonClicked(self):
        # TODO
        return
    
    pass

plugin_container.append(pluginMgr())
