import getpass
import itertools
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Union, cast

import maya
import pandas as pd
from traffic.core import Flight, Traffic
from traffic.core.time import timelike, to_datetime
from traffic.data import SO6
from traffic.plugins import PluginProvider


class _CZML_Params:
    default_time_multiplier = 100
    path_outline_width = 1
    path_width = 3
    path_lead_time = 0
    path_trail_time = 3600
    path_resolution = 5
    point_outline_width = 2
    point_pixel_size = 5
    point_height_reference = "NONE"


def format_ts(ts: pd.Timestamp) -> str:
    return maya.MayaDT(  # type: ignore
        int(ts.to_pydatetime().timestamp())
    ).rfc3339()[:-4]


def export_flight(flight: Flight) -> Iterator[Dict[str, Any]]:

    start = format_ts(flight.start)
    stop = format_ts(flight.stop)
    availability = f"{start}/{stop}"

    color = [
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        150,
    ]

    yield {
        "id": flight.callsign,
        "availability": availability,
        "position": {
            "epoch": start,
            "cartographicDegrees": list(
                itertools.chain(*flight.coords4d(delta_t=True))
            ),
        },
        "path": {
            "material": {
                "polylineOutline": {
                    "color": {"rgba": color},
                    "outlineColor": {"rgba": color},
                    "outlineWidth": _CZML_Params.path_outline_width,
                }
            },
            "width": _CZML_Params.path_width,
            "leadTime": _CZML_Params.path_lead_time,
            "trailTime": _CZML_Params.path_trail_time,
            "resolution": _CZML_Params.path_resolution,
        },
    }
    yield {
        "id": flight.callsign,
        "availability": availability,
        "position": {
            "epoch": start,
            "cartographicDegrees": list(
                itertools.chain(*flight.coords4d(delta_t=True))
            ),
        },
        "point": {
            "color": {
                "rgba": [255, 255, 255, 200]  # white center instead of color
            },
            "outlineColor": {"rgba": color},
            "outlineWidth": _CZML_Params.point_outline_width,
            "pixelSize": _CZML_Params.point_pixel_size,
            "heightReference": _CZML_Params.point_height_reference,
        },
    }


def to_czml(
    traffic: Union[Traffic, SO6],
    filename: Union[str, Path],
    minimum_time: Optional[timelike] = None,
) -> None:
    """Generates a CesiumJS scenario file."""

    if minimum_time is not None:
        minimum_time = to_datetime(minimum_time)
        traffic = cast(Traffic, traffic.query(f"timestamp >= '{minimum_time}'"))

    if isinstance(filename, str):
        filename = Path(filename)

    if not filename.parent.exists():
        filename.parent.mkdir(parents=True)

    start = format_ts(traffic.start_time)
    availability = f"{start}/{format_ts(traffic.end_time)}"
    export = [
        {
            "id": "document",
            "name": f"Traffic_{start}",
            "version": "1.0",
            "author": getpass.getuser(),
            "clock": {
                "interval": availability,
                "currentTime": start,
                "multiplier": _CZML_Params.default_time_multiplier,
            },
        }
    ]
    for flight in traffic:
        for elt in export_flight(flight):
            export.append(elt)

    with filename.open("w") as fh:
        json.dump(export, fh, indent=2)

    logging.info(f"Scenario file {filename} written")


class CesiumJS(PluginProvider):

    def load_plugin(self):
        setattr(Traffic, "to_czml", to_czml)
        setattr(SO6, "to_czml", to_czml)