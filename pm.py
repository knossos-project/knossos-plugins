from PythonQt import QtGui, Qt
import urllib, urllib2, os, urlparse, glob, time, inspect

#KNOSSOS_PLUGIN Name PluginMgr
#KNOSSOS_PLUGIN Version 1
#KNOSSOS_PLUGIN Description Plugin manager is a plugin manager

class pluginMgr:
    MANDATORY_METADATA_FIELDS = ["Name", "Version", "Description"]
    PLUGIN_LIST_COLUMNS = ["Filename"] + MANDATORY_METADATA_FIELDS
    PLUGIN_METADATA_COLUMNS = ["Field", "Content"]
    def __init__(self):
        self.twiHeadersList = []
        self.twiHash = {}
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
        localDirListLayout.addWidget(QtGui.QLabel("Plugin Metadata"), 0, 1)
        self.localDirPluginTable = QtGui.QTableWidget()
        localDirListLayout.addWidget(self.localDirPluginTable, 1, 0)
        self.setTableHeaders(self.localDirPluginTable, self.PLUGIN_LIST_COLUMNS)
        self.finalizeTable(self.localDirPluginTable)
        self.localDirMetaDataTable = QtGui.QTableWidget()
        localDirListLayout.addWidget(self.localDirMetaDataTable, 1, 1)
        self.setTableHeaders(self.localDirMetaDataTable, self.PLUGIN_METADATA_COLUMNS)
        self.finalizeTable(self.localDirMetaDataTable)
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
        repoListLayout.addWidget(QtGui.QLabel("Plugin Metadata"), 0, 1)
        self.repoPluginTable = QtGui.QTableWidget()
        repoListLayout.addWidget(self.repoPluginTable, 1, 0)
        self.setTableHeaders(self.repoPluginTable, self.PLUGIN_LIST_COLUMNS)
        self.finalizeTable(self.repoPluginTable)
        self.repoMetaDataTable = QtGui.QTableWidget()
        repoListLayout.addWidget(self.repoMetaDataTable, 1, 1)
        self.setTableHeaders(self.repoMetaDataTable, self.PLUGIN_METADATA_COLUMNS)
        self.finalizeTable(self.repoMetaDataTable)
        # Options
        optionsGroupBox = QtGui.QGroupBox("Options")
        layout.addWidget(optionsGroupBox)
        optionsLayout = QtGui.QHBoxLayout()
        optionsGroupBox.setLayout(optionsLayout)
        self.quietModeCheckBox = QtGui.QCheckBox("Quiet Mode")
        optionsLayout.addWidget(self.quietModeCheckBox)
        self.quietModeCheckBox.setChecked(False)
        self.quietModeCheckBox.setToolTip("- Silence errors\n- Skip questions with default answers")
        self.autoOverwriteCheckBox = QtGui.QCheckBox("Auto Overwrite Local")
        optionsLayout.addWidget(self.autoOverwriteCheckBox)
        self.autoOverwriteCheckBox.setChecked(True)
        self.autoOverwriteCheckBox.setToolTip("Automatically overwrite local plugins with remote,\neven when local version is same/higher than remote one")
        # Log
        logGroupBox = QtGui.QGroupBox("Log")
        layout.addWidget(logGroupBox)
        logLayout = QtGui.QVBoxLayout()
        logGroupBox.setLayout(logLayout)
        self.logTable = QtGui.QTableWidget()
        logLayout.addWidget(self.logTable)
        self.setTableHeaders(self.logTable, ["Date/Time", "Title", "Text"])
        self.finalizeTable(self.logTable)
        # Wrap it up
        self.widget.show()
        self.startUp()
        return

    def finalizeTable(self, table):
        table.horizontalHeader().setStretchLastSection(True)
        self.resizeTable(table)
        return

    def startUp(self):
        self.fillDefaults()
        self.log("Info", "Plugin manager started")
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
        del self.twiHash[table]
        return

    def resizeTable(self, table):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        return

    def addTableRow(self, table, columnTexts):
        table.insertRow(0)
        for i in xrange(len(columnTexts)):
            twi = QtGui.QTableWidgetItem(columnTexts[i])
            twi.setFlags(twi.flags() & (~Qt.Qt.ItemIsEditable))
            self.twiHeadersList.append(twi)
            table.setItem(0, i, twi)
        self.resizeTable(table)
        return

    def localDirBrowseButtonClicked(self):
        browse_dir = QtGui.QFileDialog.getExistingDirectory()
        if "" <> browse_dir:
            self.localDirEdit.setText(browse_dir)
        return
    
    def localDirDefaultButtonClicked(self):
        defaultDir = os.path.expanduser(os.path.join("~","knos_plg"))
        exists = os.path.exists(defaultDir)
        if not exists:
            choice = mb.Ok
            if not self.quietModeCheckBox.checked:
                choice = mb.question(0, "Local Default Directory", "Default directory does not exists. Create?", mb.Ok | mb.Cancel)
            if mb.Ok == choice:
                try:
                    os.makedirs(defaultDir)
                    exists = True
                except:
                    self.showMessage("Local Repository Error", "Cannot create default directory\n" + defaultDir)
        if exists:
            self.localDirEdit.setText(defaultDir)
        return

    def fillDefaults(self):
        self.localDirDefaultButtonClicked()
        self.repoDefaultButtonClicked()
        return

    def log(self, title, text):
        self.addTableRow(self.logTable, [time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()), title, text])
        return

    def showMessage(self, title, text):
        self.log(title, text)
        if not self.quietModeCheckBox.checked:
            box = QtGui.QMessageBox()
            box.setWindowTitle(title)
            box.setText(text)
            QtGui.QMessageBox.__dict__["exec"](box)
        return

    def getUrl(self, url):
        try:
            s = urllib2.urlopen(url).read()
        except:
            self.showMessage("Get URL Error", "Error reading URL:\n" + url)
            raise
        return s

    def parseMetadata(self, content):
        metadata = {}
        lines = content.split("\n")
        for line in lines:
            try:
                elems = line.split(None, 2)
            except:
                self.showMessage("here",line)
            if len(elems) < 3:
                continue
            if elems[0] <> "#KNOSSOS_PLUGIN":
                continue
            metadata[elems[1]] = elems[2]
        return metadata
    
    def processUrls(self, urls):
        plugins = {}
        for url in urls:
            try:
                content = self.getUrl(url)
                metadata = self.parseMetadata(content)
                missingMetadata = set(self.MANDATORY_METADATA_FIELDS) - set(metadata)
                if len(missingMetadata) > 0:
                    self.showMessage("Processing Error", "Plugin\n" + url + "\nMissing mandatory metadata fields:\n\n" + "\n".join(missingMetadata))
                    raise
                plugins[metadata["Name"]] = (fn, content, metadata)
            except:
                self.showMessage("Processing Error", "Error processing plugin\n" + url)
                continue
        return plugins

    def listPlugins(self, plugins, listTable, metaDataTable):
        # TODO
        return
    
    def localDirListButtonClicked(self):
        localPluginUrls = []
        localDir = self.localDirEdit.text
        localPluginUrls = [("file:" + urllib.pathname2url(fn)) for fn in glob.glob(os.path.join(localDir, "*.py"))]
        try:
            localPlugins = self.processUrls(localPluginUrls)
        except:
            self.showMessage("Local Repository Error", "Error processing repository")
            return
        self.listPlugins(localPlugins, self.localDirPluginTable, self.localDirMetaDataTable)
        return
    
    def repoDefaultButtonClicked(self):
        self.repoUrlEdit.setText("http://knossos-project.github.io/knossos-plugins/knossos_plugins.txt")
        return

    def repoListButtonClicked(self):
        try:
            repoList = self.getUrl(self.repoUrlEdit.text)
        except:
            self.showMessage("Remote Repository Error", "Error reading remote repository index")
            return
        repoPluginUrls = repoList.split("\n")
        try:
            repoPlugins = self.processUrls(repoPluginUrls)
        except:
            self.showMessage("Remote Repository Error", "Error processing repository")
            return
        self.listPlugins(repoPlugins, self.repoPluginTable, self.repoMetaDataTable)
        return
    
    def remoteToLocalButtonClicked(self):
        # TODO
        return
    
    pass

plugin_container.append(pluginMgr())
