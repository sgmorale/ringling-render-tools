"""
The hpc-spool.bat file sets up the ipy interpreter then executes this script 
with any additional arguments -- you should not call this script directly!

This standalone script must be run with IronPython (ipy.exe) since it relies on
the Microsoft Hpc .Net assemblies. It will not work if you run it using the 
regular python interpreter. 
"""

import clr, sys, os, getpass, logging, re, datetime

RRT_DEBUG = os.getenv('RRT_DEBUG',False)
RRT_USE_DESMOND = os.getenv('RRT_USE_DESMOND', False)

__LOG_LEVEL__ = logging.DEBUG if  RRT_DEBUG else logging.INFO
LOG = logging.getLogger('hpc-spool')
LOG.setLevel(__LOG_LEVEL__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)

clr.AddReference("Microsoft.Hpc.Scheduler")
clr.AddReference("Microsoft.Hpc.Scheduler.Properties")

from Microsoft.Hpc.Scheduler import *
from Microsoft.Hpc.Scheduler.Properties import *


class Spooler(object):
    REQUIRED_SERVER_VERSION = (3, 0, 2369, 0)
    RUNAS_USER = None;
    RUNAS_PASSWORD = None;
    
    @property
    def HeadNode(self):
        host = os.getenv("HEAD_NODE", None)
        if None == host: 
            LOG.error("HEAD_NODE is null - please set HEAD_NODE.")
            LOG.info("Exiting...")
            sys.exit(1)
        return host.strip()

    # Looks like Render.exe doesn't like quotes around the remote paths...
    CMD_MAYA_RENDER_SW = "Render.exe -n {threads} -r sw -s * -e * -proj {node_project} -rd {output} {scene}"
    CMD_MAYA_RENDER_RMAN = "Render.exe -n {threads} -r rman -s * -e * -proj {node_project} -rd {output} {scene}"
    CMD_3DSMAX_RENDER = "3dsmaxcmd.exe -frames=*-* -workPath:{node_project} -o:{output} -showRFW:0 {node_project}\{scene}"
    
    _renderers = {
        "max": CMD_3DSMAX_RENDER, 
        "maya_render_rman": CMD_MAYA_RENDER_RMAN,
        "maya_render_sw": CMD_MAYA_RENDER_SW
    }
    
    _confFile = None
    
    _conf = {
        "renderer": None,
        "name": None,
        "project": None,
        "node_project": None,
        "output": None,
        "logs": None,
        "scene": None,
        "start": None,
        "end": None,
        "step": "1",
        "threads": "4",
        "uuid": None,
        "net_share": None,
        "net_drive": None,
    }

    def ParseConf(self, iniPath):
        if os.path.isfile(iniPath): 
            with open(iniPath, "rb") as iniFile:
                for strLine in iniFile.readlines():
                    strLine = strLine.strip().split('#')[0]
                    if (strLine and '=' in strLine):
                        parts = strLine.split('=')
                        key = parts[0].strip()
                        val = parts[1].strip()
                        self._conf[key] = val
        else: 
            raise RuntimeError("Unable to locate " + iniPath)
        if not self._conf['uuid']:
            self._conf['uuid'] = re.sub('[%s]'% re.escape(' -:'),'', str(datetime.datetime.now()).split('.')[0])
        for k,v in self._conf.items():
            LOG.debug("%s = %s" % (k,v))

    def __init__(self, confFile):
        self._confFile = confFile
        self.ParseConf(self._confFile)
    
    def BuildTaskList(self, job):
        # this guy will need other methods to delegate to so we don't fork for each renderer available.
        render_task = job.CreateTask()
        
        node_job_dir = r"D:\hpc"
        self._conf["node_job_dir"] = node_job_dir

        node_project = os.path.join(node_job_dir, self._conf['uuid'])
        render_task.SetEnvironmentVariable("INIT_WD", node_project)
        self._conf["node_project"] = node_project

        #Main Render Task
        # basic info
        render_task.Name = "Render *"
        render_task.Type = TaskType.ParametricSweep

        #task iteration
        render_task.StartValue = int(self._conf["start"])
        render_task.EndValue = int(self._conf["end"])
        render_task.IncrementValue = int(self._conf["step"])

        # thread/node limits
        if not self._conf["renderer"] == "max":
            render_task.MinimumNumberOfCores = int(self._conf["threads"])
            render_task.MaximumNumberOfCores = int(self._conf["threads"])            

        # log redirection
        render_task.StdErrFilePath = self._conf["logs"]
        render_task.StdOutFilePath = self._conf["logs"]

        # run the render command
        render_task.CommandLine = self._renderers[self._conf["renderer"]].format(**self._conf)

        # Setup Task
        setup_task = job.CreateTask()
        setup_task.Type = TaskType.NodePrep
        setup_task.Name = "Setup"
        setup_task.CommandLine = "net use %s %s && hpc-node-prep" % (self._conf['net_drive'], self._conf['net_share'])

        # TearDown Task
        cleanup_task = job.CreateTask()
        cleanup_task.Type = TaskType.NodeRelease
        cleanup_task.Name = "Cleanup"
        cleanup_task.CommandLine = "hpc-node-release & net use %s /delete /y" % self._conf['net_drive']

        # Add Env Vars
        self.SetJobEnv(setup_task)
        self.SetJobEnv(render_task)
        self.SetJobEnv(cleanup_task)

        # Task Assignment
        job.AddTask(setup_task)
        job.AddTask(render_task)
        job.AddTask(cleanup_task)

    def SetJobEnv(self,task):
        global RRT_DEBUG
        if RRT_DEBUG: task.SetEnvironmentVariable("RRT_DEBUG", RRT_DEBUG)
        global RRT_USE_DESMOND
        if RRT_USE_DESMOND: task.SetEnvironmentVariable("RRT_USE_DESMOND", RRT_USE_DESMOND)
        
        task.SetEnvironmentVariable("MAYA_APP_DIR", self._conf["node_project"])
        task.SetEnvironmentVariable("TEMP", self._conf["node_project"])
        task.SetEnvironmentVariable("TMP", self._conf["node_project"])        
        task.SetEnvironmentVariable("OWNER", getpass.getuser())
        task.SetEnvironmentVariable("NODE_PROJECT", self._conf["node_project"])
        # script path override enables us to apply per-job dirmaps on maya jobs
        task.SetEnvironmentVariable("MAYA_SCRIPT_PATH", self._conf["node_project"]+ r"\scripts;"+os.getenv("MAYA_SCRIPT_PATH", ''))
        task.SetEnvironmentVariable("PROJECT", self._conf["project"])
        task.SetEnvironmentVariable("SCENE", self._conf["scene"])
        task.SetEnvironmentVariable("RENDERER", self._conf["renderer"])
        task.SetEnvironmentVariable("LOGS", self._conf["logs"])
        task.SetEnvironmentVariable("OUTPUT", self._conf["output"])
        task.SetEnvironmentVariable("NET_SHARE", self._conf["net_share"])
        task.SetEnvironmentVariable("NET_DRIVE", self._conf["net_drive"])

    def DoIt(self):
        scheduler = Scheduler()
        try:
            # make a connection to the cluster
            LOG.info("Connecting to cluster at: %s" % self.HeadNode)
            try:
                scheduler.Connect(self.HeadNode)
            except Exception, e:
                LOG.error("Unable to reach cluster head node: %s" % self.HeadNode)
                LOG.error(e)
                LOG.info("Exiting...")
                sys.exit(2)
            # check the cluster api version
            server_version = scheduler.GetServerVersion()
            serv = '.'.join([str(d) for d in (server_version.Major,
                              server_version.Minor,
                              server_version.Build,
                              server_version.Revision)])
            reqv = '.'.join([str(d) for d in self.REQUIRED_SERVER_VERSION])
            if serv != reqv:
                scheduler.Close()
                raise RuntimeError('HPC API mismatch: got %s, but required %s' % (serv, reqv))
            job = scheduler.CreateJob()
            # set the job properties
            job.Name = self._conf["name"]
            # task by node granularity setting for 3ds Max
            if self._conf["renderer"] == "max": 
                job.UnitType = JobUnitType.Node
            else:
                job.UnitType = JobUnitType.Core
            #job.NodeGroups.Add("ComputeNodes")
            job.IsExclusive = True
            self.BuildTaskList(job) # attach tasks to job
            
            scheduler.SubmitJob(job, self.RUNAS_USER, self.RUNAS_PASSWORD) # ship it out to the head node
            LOG.info("Submitted job %d to %s." % (job.Id, self.HeadNode))
            scheduler.Close()
        except Exception, e:
            LOG.error(e)
            LOG.error("exiting...")
            sys.exit(5)
        finally:
            scheduler.Dispose()
        sys.exit(0)


# Command Line Entry Point
def main():
    LOG.info('Starting hpc-spool for MS HPC v'+'.'.join([str(v) for v in Spooler.REQUIRED_SERVER_VERSION]))
    conf_path = None
    try:
        conf_path = os.path.abspath(sys.argv[1])
    except IndexError:
        LOG.error("Must specify an ini file.")
        LOG.info("Exiting...")
        sys.exit(3)
    LOG.info("Spooling job from %s" % conf_path)
    try:
        spool = Spooler(conf_path)
        spool.DoIt()
    except Exception, e:
        LOG.error(e)
        sys.exit(-1)

if '__main__' == __name__:
    main()
