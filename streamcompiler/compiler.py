import scfg
import re

from datetime import timedelta
from pathlib import Path
from typing import Dict, Optional, List
from gi.repository import GLib, Gst, GES, GstPbutils

from .asset import AssetCollection
from .future import Future
from .profile import Profile


def parse_timedelta(delta: str) -> timedelta:
    match = re.match('(?:([0-9]+)s)?(?:([0-9]+)ms)?', delta)
    if not match:
        raise ValueError(f"Invalid time delta: {delta}")

    return timedelta(
        seconds=int(match.group(1) or 0),
        milliseconds=int(match.group(2) or 0)
    )


def compiler_test(assets: AssetCollection, config: scfg.Config, *, preview=False) -> Future[GES.Pipeline]:
    timeline = GES.Timeline.new_audio_video()
    layer = timeline.append_layer()

    def stage1():
        return Future.gather(
            [assets.add_from_input(input) for input in config.get_all('input')],
        ).then(stage2)

    def stage2(_assets: List[GES.Asset]):
        pos = timedelta(seconds=0)
        inputoffsets: Dict[str, timedelta] = {}
        track = config.get('track')
        if not track:
            return
        for clip in track.get_all('clip'):
            inputd = clip.get('input')
            if not inputd:
                continue
            input_name = inputd.params[0]

            offsetd = clip.get('offset')
            if offsetd:
                offset = parse_timedelta(offsetd.params[0])
            else:
                offset = inputoffsets.get(input_name, timedelta(seconds=0))

            durationd = clip.get('duration')
            if durationd:
                duration = parse_timedelta(durationd.params[0])
            else:
                duration = timedelta(seconds=2)

            inputoffsets[inputd.params[0]] = offset + duration

            print(f"Adding {input_name} @ {pos} ; Offset {offset} Duration {duration}")
            asset = assets[input_name]
            nanoduration = int((duration / timedelta(microseconds=1)) * 1_000)
            nanooffset = int((offset / timedelta(microseconds=1)) * 1_000)
            nanopos = int((pos / timedelta(microseconds=1)) * 1_000)
            layer.add_asset(
                asset,
                nanopos,
                nanooffset,
                nanoduration,
                GES.TrackType.UNKNOWN
            )
            pos += duration

        ## Configure pipeline
        pipeline = GES.Pipeline.new()
        pipeline.set_timeline(timeline)

        if preview:
            pipeline.set_mode(GES.PipelineFlags.FULL_PREVIEW)
        else:
            outputd = config.get('output')
            profile = Profile.from_config(outputd)
            output_path = None
            if outputd:
                output_pathd = outputd.get('path')
                if output_pathd:
                    output_path = Path(output_pathd.params[0])
            if not output_path:
                config_path = Path(config.filename)
                output_path = config_path.with_suffix(f'.{profile.file_extension}')
            output_uri = Gst.filename_to_uri(str(output_path))
            if not pipeline.set_render_settings(output_uri , profile.container_profile):
                raise RuntimeError("Failed to set render settings")
            pipeline.set_mode(GES.PipelineFlags.SMART_RENDER)
            print(f"Rendering to {output_path}")

        return pipeline

    return stage1()
