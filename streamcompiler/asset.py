import scfg

from typing import Dict
from gi.repository import Gst, GES

from .future import Future


class AssetCollection:
    project: GES.Project
    assets: Dict[str, str]
    futures: Dict[str, Future[GES.Asset]]

    def __init__(self, project: GES.Project) -> None:
        self.project = project
        self.assets = {}
        self.futures = {}

        project.connect('asset-added', self._asset_added)
        project.connect('error-loading-asset', self._error_loading_asset)

    def add_from_input(self, input: scfg.Directive) -> Future[GES.Asset]:
        future: Future[GES.Asset] = Future()

        name, = input.params
        path = input.get('path')
        if not path:
            raise ValueError("Missing property: path")
        uri = Gst.filename_to_uri(path.params[0])
        self.project.create_asset(uri, GES.UriClip)
        self.assets[name] = uri

        self.futures[uri] = future
        return future

    def __getitem__(self, name: str) -> GES.Asset:
        asset_id = self.assets[name]
        return self.project.get_asset(asset_id, GES.UriClip)

    def _asset_added(self, project, asset) -> None:
        future = self.futures.pop(asset.get_id())
        future.set_result(asset)

    def _error_loading_asset(self, project, error, id, extractable_type) -> None:
        future = self.futures.pop(id)
        future.set_exception(error)

