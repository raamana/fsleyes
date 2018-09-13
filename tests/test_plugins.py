#!/usr/bin/env python
#
# test_plugins.py -
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#

import sys

import textwrap as tw

import os.path as op

import pkg_resources

import fsl.utils.tempdir  as tempdir
import fsl.utils.settings as fslsettings
import fsleyes.plugins    as plugins


plugindirs = ['fsleyes_plugin_example', 'fsleyes_plugin_bad_example']
plugindirs = [op.join(op.dirname(__file__), 'testdata', d) for d in plugindirs]
plugindirs = [op.abspath(d)                                for d in plugindirs]


def setup_module():
    for d in plugindirs:
        pkg_resources.working_set.add_entry(d)
    import fsleyes_plugin_example      # noqa
    import fsleyes_plugin_bad_example  # noqa


def test_listPlugins():
    # this will break if more plugins
    # are installed in the test environment
    assert sorted(plugins.listPlugins()) == [
        'fsleyes-plugin-bad-example', 'fsleyes-plugin-example']


def test_listViews():
    from fsleyes_plugin_example.plugin import PluginView

    views = dict(plugins.listViews())

    assert views == {'Plugin view' : PluginView}


def test_listControls():
    from fsleyes_plugin_example.plugin import PluginControl
    from fsleyes.views.timeseriespanel import TimeSeriesPanel
    from fsleyes.views.orthopanel      import OrthoPanel

    ctrls      = dict(plugins.listControls())
    ctrlsortho = dict(plugins.listControls(OrthoPanel))
    ctrlsts    = dict(plugins.listControls(TimeSeriesPanel))

    assert ctrls      == {'Plugin control' : PluginControl}
    assert ctrlsortho == {'Plugin control' : PluginControl}
    assert ctrlsts    == {}


def test_listTools():
    from fsleyes_plugin_example.plugin import PluginTool

    tools = dict(plugins.listTools())

    assert tools == {'Plugin tool' : PluginTool}


code = tw.dedent("""
from fsleyes.views.viewpanel       import ViewPanel
from fsleyes.controls.controlpanel import ControlPanel
from fsleyes.actions               import Action

class {prefix}View(ViewPanel):
    pass

class {prefix}Control(ControlPanel):
    pass

class {prefix}Tool(Action):
    pass
""").strip()


def test_loadPlugin():
    with tempdir.tempdir(changeto=False) as td:
        with open(op.join(td, 'test_loadplugin.py'), 'wt') as f:
            f.write(code.format(prefix='Load'))

        plugins.loadPlugin(op.join(td, 'test_loadplugin.py'))

        mod = sys.modules['fsleyes_plugin_test_loadplugin']

        assert 'fsleyes-plugin-test-loadplugin' in plugins.listPlugins()
        assert plugins.listTools()[   'LoadTool']    is mod.LoadTool
        assert plugins.listControls()['LoadControl'] is mod.LoadControl
        assert plugins.listViews()[   'LoadView']    is mod.LoadView


def test_installPlugin():
    with tempdir.tempdir() as td:

        with open('test_installplugin.py', 'wt') as f:
            f.write(code.format(prefix='Install'))

        s = fslsettings.Settings('test_plugins', cfgdir=td, writeOnExit=False)
        with fslsettings.use(s):

            plugins.installPlugin('test_installplugin.py')

            mod = sys.modules['fsleyes_plugin_test_installplugin']

            assert 'fsleyes-plugin-test-installplugin' in plugins.listPlugins()
            assert plugins.listTools()[   'InstallTool']    is mod.InstallTool
            assert plugins.listControls()['InstallControl'] is mod.InstallControl
            assert plugins.listViews()[   'InstallView']    is mod.InstallView
            assert op.exists(op.join(td, 'plugins', 'test_installplugin.py'))
