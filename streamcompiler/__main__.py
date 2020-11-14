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
from .future import Future, run_soon


parser = argparse.ArgumentParser()
parser.add_argument('config', type=argparse.FileType('r'))
parser.add_argument('-p', '--preview', action='store_true')
parser.add_argument('--dry-run', action='store_true')

args = parser.parse_args()
loop = GLib.MainLoop()


def asset_added(project, asset) -> None:
    info = asset.get_info()
    video, = info.get_video_streams()
    print(f"Asset added {asset.get_id()} {video.get_width()}x{video.get_height()}@{video.get_framerate_num()//1_000}")


def asset_loading(project, asset) -> None:
    print(f"Asset loading {asset.get_id()}")


def run_pipeline(element: GES.Pipeline) -> None:
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

    if args.dry_run:
        print("This is a dry-run")
        run_soon(loop.quit)
        return
    result = element.set_state(Gst.State.PLAYING)
    if result == Gst.StateChangeReturn.FAILURE:
        print("Failed to change pipeline to playing state")
        run_soon(loop.quit)
        return
    bus = element.get_bus()
    bus.add_signal_watch()
    bus.connect('message', bus_message)


def finish(fut: Future[None]) -> None:
    try:
        fut.result()
    except:
        run_soon(loop.quit)
        raise


def run_compiler() -> None:
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
        compilefut = compiler_test(assets, config, preview=args.preview)
        compilefut.then(run_pipeline).add_done_callback(finish)
    except:
        run_soon(loop.quit)
        raise


def main():
    run_soon(run_compiler)
    loop.run()
