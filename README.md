# stream-compiler

A video editor based on a human writeable script language.

A script language describes how multiple media sources should be combined.
Stream-compiler takes this textual description and creates a single video
output.

All the heavy lifting of actually decoding, encoding, compositing, etc is done
using GStreamer (GST) and GStreamer Editing Services (GES).

See also `ges-launch-1.0` that expose all the features of GES but in a not so
user friendly format.

## Example

Video script - my-video.conf
```
input foo {
    path "~/Videos/some-video.mp4"
}
input bar {
    path "~/Videos/other-video.mp4"
}
input icon {
    path "~/Pictures/icon.png"
}
output {
    container "video/webm"
    video "video/x-vp9"
}
# This track defines a small icon that is displayed over the other media for
# the full duration
track {
    clip {
        input icon
        duration 12s
        opacity 0.2
        scale 0.2
        position top-right
    }
}
# This track plays short extracts of the two video inputs after each other
track {
    clip {
        input bar
        # Start 1 second into the source media (default: 0)
        offset 1s
        # Play for 3 seconds
        duration 3s
    }
    clip {
        input foo
        offset 122s
        duration 2s
    }
    clip {
        # The 2nd time the clip is used playback starts from where it left off
        input bar
        duration 4s
    }
    clip {
        input foo
        duration 3s
    }
}
```

Render the video

```bash
streamc myvideo.conf
```
