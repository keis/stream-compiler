from __future__ import annotations

import scfg

from typing import Optional
from gi.repository import Gst, GstPbutils


class Profile:
    container_profile: GstPbutils.EncodingContainerProfile
    video_profile: GstPbutils.EncodingVideoProfile
    audio_profile: GstPbutils.EncodingAudioProfile

    def __init__(self, container_profile: GstPbutils.EncodingContainerProfile) -> None:
        self.container_profile = container_profile
        for profile in container_profile.get_profiles():
            if isinstance(profile, GstPbutils.EncodingVideoProfile):
                self.video_profile = profile
            elif isinstance(profile, GstPbutils.EncodingAudioProfile):
                self.audio_profile = profile
            else:
                raise RuntimeError(f"Unknown subprofile type: {type(profile)}")

    @classmethod
    def from_config(cls, outputd: Optional[scfg.Directive]) -> Profile:
        containerd = outputd and outputd.get('container')
        containerformat = containerd.params[0] if containerd else 'application/ogg'
        container_profile = GstPbutils.EncodingContainerProfile.new(
            "stream-compiler-profile",
            "stream-compiler encoding profile",
            Gst.Caps.from_string(containerformat),
            None
        )

        videod = outputd and outputd.get('video')
        videoformat = videod.params[0] if videod else 'video/x-theora'
        width, height = 1280, 720
        video_profile = GstPbutils.EncodingVideoProfile.new(
            Gst.Caps.from_string(videoformat),
            None,
            Gst.Caps.from_string(f'video/x-raw,width={width},height={height}'),
            0
        )

        audiod = outputd and outputd.get('audio')
        audioformat = audiod.params[0] if audiod else 'audio/x-vorbis'
        audio_profile = GstPbutils.EncodingAudioProfile.new(
            Gst.Caps.from_string(audioformat),
            None,
            Gst.Caps.from_string('audio/x-raw'),
            0
        )

        container_profile.add_profile(video_profile)
        container_profile.add_profile(audio_profile)

        return cls(container_profile)

    @property
    def file_extension(self) -> Optional[str]:
        return self.container_profile.get_file_extension()

    @property
    def video_width(self) -> Optional[int]:
        res = self.video_profile.get_restriction()
        structure = res.get_structure(0)
        return structure.get_value('width')

    @property
    def video_height(self) -> Optional[int]:
        res = self.video_profile.get_restriction()
        structure = res.get_structure(0)
        return structure.get_value('height')
