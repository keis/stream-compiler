import gi
gi.require_version('Gst', '1.0')
gi.require_version('GES', '1.0')
from gi.repository import GLib, Gst, GES

Gst.init()
GES.init()

import argparse
import scfg
from .compiler import compiler_test
from .asset import AssetCollection


parser = argparse.ArgumentParser()
parser.add_argument('config', type=argparse.FileType('r'))
parser.add_argument('-p', '--preview', action='store_true')
parser.add_argument('--dry-run', action='store_true')

args = parser.parse_args()


def asset_added(project, asset) -> None:
    info = asset.get_info()
    video, = info.get_video_streams()
    print(f"Asset added {asset.get_id()} {video.get_width()}x{video.get_height()}@{video.get_framerate_num()//1_000}")


def asset_loading(project, asset) -> None:
    print(f"Asset loading {asset.get_id()}")


def quit() -> bool:
    loop.quit()
    return False


def run() -> bool:
    def bus_message(bus, message) -> None:
        if message.type == Gst.MessageType.EOS:
            print("End of stream")
            element.set_state(Gst.State.NULL)
            loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err} {debug}")
            element.set_state(Gst.State.NULL)
            loop.quit()
        elif message.type == Gst.MessageType.STATE_CHANGED:
            oldstate, newstate, pending = message.parse_state_changed()
            #print(f'State {message.src.name}: {oldstate.value_nick} -> <{newstate.value_nick}> -> {pending.value_nick}')

    config = scfg.Config(args.config.name)
    config.load()

    project = GES.Project.new(None)
    project.connect('asset-added', asset_added)
    project.connect('asset-loading', asset_loading)
    project.connect(
        'error-loading-asset',
        lambda project, error, id, exctractable_type: print("Error loading", project, id, error))

    assets = AssetCollection(project)

    try:
        element = compiler_test(assets, config, preview=args.preview)
    except:
        GLib.idle_add(quit)
        raise

    if args.dry_run:
        print("This is a dry-run")
        GLib.idle_add(quit)
        return False
    result = element.set_state(Gst.State.PLAYING)
    if result == Gst.StateChangeReturn.FAILURE:
        print("Failed to change pipeline to playing state")
        GLib.idle_add(quit)
        return False
    bus = element.get_bus()
    bus.add_signal_watch()
    bus.connect('message', bus_message)

    return False

GLib.idle_add(run)

loop = GLib.MainLoop()
loop.run()
