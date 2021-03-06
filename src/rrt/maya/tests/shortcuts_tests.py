import unittest
import pymel
from ludibrio import Stub
from rrt.maya.shortcuts import scene_is_dirty, get_job_type, get_scene_name, \
    get_frame_range

class TestShortcuts(unittest.TestCase):
    """
    Perhaps not a great test of the whole system, but at least it's repeatable.
    We're using a stub/mock package to force pymel to return canned responses.
    These tests simply show rrt's responses to external stimuli. 
    """
    
    def test_scene_is_dirty(self):
        with Stub() as pymel.core.language:
            from pymel.core.language import mel
            mel.eval('file -q -mf') >> 0
        self.assertFalse(scene_is_dirty())
        
        with Stub() as pymel.core.language:
            from pymel.core.language import mel
            mel.eval('file -q -mf') >> 1
        self.assertTrue(scene_is_dirty())
    
    def test_get_job_type(self):
        with Stub() as pymel.core.general:
            from pymel.core.general import SCENE
            SCENE.defaultRenderGlobals.currentRenderer.get() >> 'renderMan'
        self.assertEquals(get_job_type(),'maya_render_rman')
        with Stub() as pymel.core.general:
            from pymel.core.general import SCENE
            SCENE.defaultRenderGlobals.currentRenderer.get() >> 'anything else'
        self.assertEquals(get_job_type(),'maya_render_sw')
    
    def test_get_scene_name(self):
        with Stub() as pymel.core.system:
            from pymel.core.system import sceneName
            sceneName() >> "S:/foo/bar.ext"
        self.assertEquals(get_scene_name(),'bar')
        with Stub() as pymel.core.system:
            from pymel.core.system import sceneName
            sceneName() >> "S:\\foo\\bar.ext"
        self.assertEquals(get_scene_name(),'bar')
        
        with Stub() as pymel.core.system:
            from pymel.core.system import sceneName
            sceneName() >> "S:/foo/bar_no_ext"
        self.assertEquals(get_scene_name(),'bar_no_ext')
    
    def test_get_frame_range(self):
        with Stub() as pymel.core.general:
            from pymel.core.general import SCENE
            SCENE.defaultRenderGlobals.startFrame.get() >> 10.0
            SCENE.defaultRenderGlobals.endFrame.get() >> 42.0
        frange = get_frame_range()
        self.assertEqual(frange[0],10)
        self.assertEqual(frange[1],42)
        for val in frange:
            self.assertTrue(isinstance(val, int))
