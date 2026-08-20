#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sys import exit
from typing import Dict, List

import pystac


@dataclass
class Arguments:
    inputs: List[Path]
    output: Path


if __name__ == "__main__":
    praser = ArgumentParser()
    praser.add_argument("--inputs", nargs="+", type=Path, required=True, help="")
    praser.add_argument(
        "--output",
        nargs=1,
        type=Path,
        required=False,
        default=Path("stac-catalog"),
        help="",
    )

    parsed_args: Arguments = Arguments(**vars(praser.parse_args()))

    parsed_args.output.mkdir(parents=False, exist_ok=False)

    catalog: pystac.Catalog = pystac.Catalog(
        id="eoap-output-catalog",
        description="Simplistic output STAC Catalog",
        href=Path(parsed_args.output, "catalog.json"),
        catalog_type=pystac.CatalogType.SELF_CONTAINED,
    )

    for input_file in parsed_args.inputs:
        item = pystac.item.Item(
            id=input_file.stem,
            geometry=None,
            bbox=None,
            datetime=datetime.now(),
            properties={},
            assets={input_file.stem: pystac.asset.Asset(href=input_file)},
        )

        catalog.add_item(item)

        assets: Dict[str, pystac.asset.Asset] = item.get_assets()
        copied_assets: Dict[str, pystac.asset.Asset] = {}

        for asset_id, asset in assets.items():
            new_asset_path: Path = Path(
                Path(item.get_self_href()).parent, input_file.name
            )
            new_asset_path.parent.mkdir()
            item.add_asset(asset_id, asset.copy(str(new_asset_path)))

    catalog.make_all_asset_hrefs_relative()

    catalog.save()

    exit(0)
