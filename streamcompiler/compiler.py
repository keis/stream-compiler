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


def create_timeline(profile: Profile) -> GES.Timeline:
    timeline = GES.Timeline.new()
    audio_track = GES.AudioTrack.new()
    video_track = GES.VideoTrack.new()
    video_track.set_restriction_caps(
        Gst.Caps.from_string(f'video/x-raw,width={profile.video_width},height={profile.video_height}'))

    timeline.add_track(video_track)
    timeline.add_track(audio_track)

    return timeline


def process_track(profile: Profile, assets: AssetCollection, layer: GES.Layer, trackd: scfg.Directive) -> None:
    pos = timedelta(seconds=0)
    inputoffsets: Dict[str, timedelta] = {}

    for clipd in trackd.get_all('clip'):
        inputd = clipd.get('input')
        if not inputd:
            continue
        input_name = inputd.params[0]

        offsetd = clipd.get('offset')
        if offsetd:
            offset = parse_timedelta(offsetd.params[0])
        else:
            offset = inputoffsets.get(input_name, timedelta(seconds=0))

        durationd = clipd.get('duration')
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
        clip = layer.add_asset(
            asset,
            nanopos,
            nanooffset,
            nanoduration,
            GES.TrackType.UNKNOWN
        )

        opacityd = clipd.get('opacity')
        if opacityd:
            opacity = float(opacityd.params[0])
            transparency_effect = GES.Effect.new(f'frei0r-filter-transparency transparency={opacity}')
            clip.add_top_effect(transparency_effect, -1)

        scaled = clipd.get('scale')
        if scaled:
            scale = float(scaled.params[0])
            info = asset.get_info()
            video, = info.get_video_streams()
            _ok, width = clip.get_child_property('width')
            _ok, height = clip.get_child_property('height')
            clip.set_child_property('width', int(width * scale))
            clip.set_child_property('height', int(height * scale))

        positiond = clipd.get('position')
        if positiond:
            position = positiond.params[0]

            _ok, elemwidth = clip.get_child_property('width')
            _ok, elemheight = clip.get_child_property('height')

            videowidth, videoheight = profile.video_width, profile.video_height
            if position == 'bottom-right':
                clip.set_child_property('posx', videowidth - elemwidth)
                clip.set_child_property('posy', videoheight - elemheight)
            elif position == 'bottom-left':
                clip.set_child_property('posx', 0)
                clip.set_child_property('posy', videoheight - elemheight)
            elif position == 'top-right':
                clip.set_child_property('posx', videowidth - elemwidth)
                clip.set_child_property('posy', 0)
            elif position == 'top-left':
                clip.set_child_property('posx', 0)
                clip.set_child_property('posy', 0)
            else:
                raise ValueError(f"Unknown position {position}")

        pos += duration


def compiler_test(assets: AssetCollection, config: scfg.Config, *, preview=False) -> Future[GES.Pipeline]:
    profile = Profile.from_config(config.get('output'))
    timeline = create_timeline(profile)

    def stage1():
        return Future.gather(
            [assets.add_from_input(input) for input in config.get_all('input')],
        ).then(stage2)

    def stage2(_assets: List[GES.Asset]):
        for track in config.get_all('track'):
            layer = timeline.append_layer()
            process_track(profile, assets, layer, track)

        ## Configure pipeline
        pipeline = GES.Pipeline.new()
        pipeline.set_timeline(timeline)

        if preview:
            pipeline.set_mode(GES.PipelineFlags.FULL_PREVIEW)
        else:
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
            print(f"Rendering to {output_path} {profile.video_width}x{profile.video_height}")

        return pipeline

    return stage1()
