import gi
gi.require_version('Gst', '1.0')
gi.require_version('GES', '1.0')
from gi.repository import GLib, Gst, GES

Gst.init()
GES.init()

import argparse
import scfg

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Optional, Union
from time import time
from pathlib import Path

from .asset import AssetCollection
from .compiler import compile
from .future import Future, run_soon
from .profile import Profile


parser = argparse.ArgumentParser()
parser.add_argument('config', type=argparse.FileType('r'))
parser.add_argument('-p', '--preview', action='store_true')
parser.add_argument('--dry-run', action='store_true')

args = parser.parse_args()
loop = GLib.MainLoop()


@dataclass(frozen=True)
class Output:
    mode: GES.PipelineFlags
    path: Optional[Path]


def asset_added(project, asset: GES.Asset) -> None:
    info = asset.get_info()
    audio, = info.get_audio_streams()
    video, = info.get_video_streams()
    vformat = video.get_caps().get_structure(0).get_name()
    aformat = audio.get_caps().get_structure(0).get_name()
    print(f"Asset added {asset.get_id()} {video.get_width()}x{video.get_height()}@{video.get_framerate_num()//1_000} {vformat} {aformat}")


def asset_loading(project, asset) -> None:
    print(f"Asset loading {asset.get_id()}")


def watch_position(element, callback: Callable[[int], None]) -> None:
    def watch():
        status, current = element.query_position(Gst.Format.TIME)
        if status:
            callback(current)
        return True
    GLib.timeout_add(1000, watch)


def pretty_filesize(size: Union[int, float]) -> str:
    for unit in ('', 'Ki', 'Mi', 'Gi'):
        if size < 1024:
            break
        size /= 1024
    return f"{size:.2f}{unit}B"


def run_pipeline(pipeline: GES.Pipeline, output: Output) -> None:
    def bus_message(bus, message) -> None:
        if message.type == Gst.MessageType.EOS:
            print("End of stream")
            pipeline.set_state(Gst.State.NULL)
            loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err} {debug}")
            pipeline.set_state(Gst.State.NULL)
            loop.quit()
        elif message.type == Gst.MessageType.STATE_CHANGED:
            oldstate, newstate, pending = message.parse_state_changed()
            #print(f'State {message.src.name}: {oldstate.value_nick} -> <{newstate.value_nick}> -> {pending.value_nick}')

    def position_changed(nanoposition) -> None:
        fraction = min(nanoposition, duration) / duration
        position = timedelta(microseconds=nanoposition / 1_000)

        filesize = output.path.stat().st_size
        estimatedsize = filesize * (duration // nanoposition)
        if filesize > 2e6:
            print(
                f"\r{fraction*100:.2f}% - {position} / {endposition}"
                f" - {pretty_filesize(filesize)} / ~{pretty_filesize(estimatedsize)}",
                end='')
        else:
            print(f"\r{fraction*100:.2f}% - {position} / {endposition}", end='')

    timeline = pipeline.props.timeline
    duration = timeline.props.duration
    endposition = timedelta(microseconds=duration / 1_000)

    if args.dry_run:
        print("This is a dry-run")
        run_soon(loop.quit)
        return

    result = pipeline.set_state(Gst.State.PLAYING)
    if result == Gst.StateChangeReturn.FAILURE:
        print("Failed to change pipeline to playing state")
        run_soon(loop.quit)
        return

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect('message', bus_message)
    if output.path:
        watch_position(pipeline, position_changed)


def configure_preview(pipeline: GES.Pipeline) -> Output:
    pipeline.set_mode(GES.PipelineFlags.FULL_PREVIEW)
    return Output(mode=GES.PipelineFlags.FULL_PREVIEW, path=None)


def configure_render(config: scfg.Config, profile: Profile, pipeline: GES.Pipeline) -> Output:
    outputd = config.get('output')
    output_path = None

    if outputd:
        output_pathd = outputd.get('path')
        if output_pathd:
            output_path = Path(output_pathd.params[0])

    if not output_path:
        config_path = Path(config.filename)
        output_path = config_path.with_suffix(f'.{profile.file_extension}')

    output_uri = output_path.resolve().as_uri()
    if not pipeline.set_render_settings(output_uri , profile.container_profile):
        raise RuntimeError("Failed to set render settings")

    pipeline.set_mode(GES.PipelineFlags.SMART_RENDER)

    return Output(mode=GES.PipelineFlags.SMART_RENDER, path=output_path)


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

    def after_compile(timeline: GES.Timeline) -> None:
        # Configure pipeline
        pipeline = GES.Pipeline.new()
        pipeline.set_timeline(timeline)

        output = configure_preview(pipeline) if args.preview else configure_render(config, profile, pipeline)
        if output.path:
            print(f"Rendering to {output.path} {profile.video_width}x{profile.video_height}")

        run_pipeline(pipeline, output)


    try:
        profile = Profile.from_config(config.get('output'))
        compilefut = compile(config, profile, assets)
        compilefut.then(after_compile).add_done_callback(finish)
    except:
        run_soon(loop.quit)
        raise


def main():
    run_soon(run_compiler)
    loop.run()


if __name__ == '__main__':
    main()
