import scfg

from typing import Dict
from gi.repository import Gst, GES


class AssetCollection:
    project: GES.Project
    assets: Dict[str, str]

    def __init__(self, project: GES.Project) -> None:
        self.project = project
        self.assets = {}

    def add_from_input(self, input: scfg.Directive) -> None:
        name, = input.params
        path = input.get('path')
        if not path:
            raise ValueError("Missing property: path")
        uri = Gst.filename_to_uri(path.params[0])
        self.project.create_asset(uri, GES.UriClip)
        GES.UriClip.new(uri)
        self.assets[name] = uri

    def __getitem__(self, name: str) -> GES.Asset:
        asset_id = self.assets[name]
        return self.project.get_asset(asset_id, GES.UriClip)
