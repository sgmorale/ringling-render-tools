import sys, os, zipfile, getpass, re, textwrap
from PyQt4 import QtGui, QtCore
from rrt.max.ui.submit import Ui_SubmitMainWindow
from rrt.jobspec import JobSpec
from rrt.settings import JOB_OUTPUT_UNC

IMAGE_EXT = [
#    '.avi', 
    '.bmp', 
    '.cin', 
    '.eps', '.ps', 
    '.exr', '.fxr', '.hdr', 
    '.pic', 
    '.jpg', '.jpe', '.jpeg', 
    '.png', 
    '.rgb', '.rgba', 
    '.sgi', '.int', '.inta', '.bw', 
    '.rla', 
    '.rpf', 
    '.tga', '.vda', '.icb', 
    '.vst', 
    '.tif', 
    '.dds'
]
class SubmitGui(QtGui.QDialog, Ui_SubmitMainWindow):
    def __init__(self, parent=None):
        super(SubmitGui, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle('hpc-submit-max')
        self.setWindowIcon(QtGui.QIcon("C:/Ringling/hpc/icons/hpcicon3-01.png"))
        self.output_ext_field.addItems(sorted(IMAGE_EXT))
        self._setup_validators()

    def _setup_validators(self):
        """
        Regex validators for title/output
        """
        self.title_field.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('^[A-Za-z0-9_\-\s]+$'), self))
        self.output_base_field.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('^[A-Za-z0-9_\-\.]+$'), self))
        
    def browse(self):
        filename = QtGui.QFileDialog.getOpenFileName(directory='Z:\\', filter="*.zip")
        if filename:
            self.scene_field.clear()
            self.project_field.setText(filename)
            zf = zipfile.ZipFile(open(filename,'rb'))
            self.scene_field.addItems([f for f in zf.namelist() if f.lower().endswith('.max')])
    
    @property
    def job_data(self):
        job_uuid = JobSpec.new_uuid()
        start_frame = min((int(self.start_field.value()), int(self.end_field.value())))
        end_frame = max((int(self.start_field.value()), int(self.end_field.value())))
        image_filename = str(self.output_base_field.text()) + str(self.output_ext_field.currentText())
        return {
                'renderer'  : 'max',
                'title'     : str(self.title_field.text()), 
                'uuid'      : job_uuid,
                'project'   : os.path.normpath(str(self.project_field.text())),
                'scene'     : str(self.scene_field.currentText()),
                'output'    : os.path.join(JOB_OUTPUT_UNC, getpass.getuser(), 
                                           job_uuid, 
                                           image_filename),
                'start'     : start_frame,
                'end'       : end_frame,
                'step'      : str(self.step_field.value()),
                'threads'   : 0
                }
    
    def submit_job(self):
        try:
            spec = JobSpec(**self.job_data)
            # TODO: find a better place to do this.
            if not str(self.output_base_field.text()):
                raise RuntimeError("Output cannot be blank.")
            spec.submit_job()
            self.quit()
        except Exception, e:
            alert = QtGui.QMessageBox(self)
            alert.setWindowTitle('Error')
            alert.setIcon(QtGui.QMessageBox.Warning)
            alert.setText(str(e))
            alert.exec_()
    
    def quit(self): 
        self.done(0)

def submit_gui():
    app = QtGui.QApplication(sys.argv)
    gui = SubmitGui()
    gui.show()
    sys.exit(app.exec_())
    
if __name__ == '__main__': submit_gui()
