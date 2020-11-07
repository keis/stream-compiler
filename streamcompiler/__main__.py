import gi
gi.require_version('Gst', '1.0')
gi.require_version('GES', '1.0')
from gi.repository import GLib, Gst, GES

Gst.init()
GES.init()

import argparse
import scfg
from .compiler import compiler_test


parser = argparse.ArgumentParser()
parser.add_argument('config', type=argparse.FileType('r'))
parser.add_argument('-p', '--preview', action='store_true')

args = parser.parse_args()

def run():
    def bus_message(bus, message):
        if message.type == Gst.MessageType.EOS:
            print("End of stream")
            element.set_state(Gst.State.NULL)
            loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err} {debug}")
            element.set_state(Gst.State.NULL)
            loop.quit()

    config = scfg.Config(args.config.name)
    config.load()

    project = GES.Project.new(None)
    project.connect(
        'asset-added',
        lambda project, asset: print(f"Asset added {asset.get_id()}"))
    project.connect(
        'asset-loading',
        lambda project, asset: print(f"Asset loading {asset.get_id()}"))
    project.connect(
        'error-loading-asset',
        lambda project, error, id, exctractable_type: print("Error loading", project, id, error))
    element = compiler_test(project, config, preview=args.preview)
    if element:
        element.set_state(Gst.State.PLAYING)
        bus = element.get_bus()
        bus.add_signal_watch()
        bus.connect('message', bus_message)
    else:
        loop.quit()

    return False

GLib.idle_add(run)

loop = GLib.MainLoop()
loop.run()
