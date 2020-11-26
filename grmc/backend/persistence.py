import os
from glob import glob

import pandas as pd
from PIL import Image
from pandas import DataFrame
from typing import Iterable, Optional, Any, Tuple, Union

from grmc.backend.cache import ScenarioCache
from grmc.representation.scenario import Scenario, Modality, Signal
from grmc.representation.util import unmarshal, marshal

ANNOTATION_TOOL_ID = "annotation_tool"

_MAX_GUESS_RANGE = 60 * 60 * 24 * 365 * 100


def _get_base():
    return "webapp/src/assets"


def file_name(path):
    return os.path.splitext(base_name(path))[0]


def base_name(path):
    return os.path.basename(path)


def _get_path(scenario_name, modality: Optional[Union[Modality, str]] = None, file: str = None, extension: Optional[str] = ".json"):
    path = os.path.join(_get_base(), scenario_name)
    if modality:
        path = os.path.join(path, modality if isinstance(modality, str) else modality.name.lower())
    else:
        path = os.path.join(path, scenario_name)

    if file:
        path = os.path.join(path, file)

    return path + extension if extension else path


def load_text(scenario_id: str) -> DataFrame:
    text_path = _get_path(scenario_id, Modality.TEXT, extension=None)
    csv_files = tuple(glob(os.path.join(text_path, "*.csv")))

    return pd.concat(_load_csv(file) for file in csv_files) if csv_files else pd.DataFrame()


def _load_csv(file):
    data = pd.read_csv(file, skipinitialspace=True)
    data['chat'] = file_name(file)
    data['file'] = Modality.TEXT.name.lower() + "/" + base_name(file) + "#"
    data['file'] = data['file'] + data.index.astype(str)

    return data


def load_images(scenario: Scenario) -> DataFrame:
    image_path = _get_path(scenario.id, Modality.IMAGE, extension=None)
    images = glob(os.path.join(image_path, "*"))

    return pd.DataFrame([get_image_meta(image, scenario) for image in images],
                        columns=["file", "time", "bounds"])


def get_image_meta(image: str, scenario: Scenario) -> Tuple[int, Tuple[int, int, int ,int]]:
    base = base_name(image)
    name = file_name(base)
    # Path in file system
    image_path = _get_path(scenario.id, Modality.IMAGE, base, extension=None)
    # Path in scenario
    image_file = Modality.IMAGE.name.lower() + "/" + base

    timestamp = _guess_timestamp(name, scenario.start, scenario.end)

    if not os.path.isfile(image_path):
        return None

    with Image.open(image_path) as img:
        bounds = (0, 0) + img.size

    return image_file, timestamp, bounds


def guess_scenario_range(scenario_id: str, modalities: Iterable[str]):
    min_ = _MAX_GUESS_RANGE
    max_ = 0

    if Modality.IMAGE.name.lower() in modalities:
        image_path = _get_path(scenario_id, Modality.IMAGE, extension=None)
        for image in glob(os.path.join(image_path, "*")):
            image_name = os.path.splitext(os.path.basename(image))[0]
            image_timestamp = _guess_timestamp(image_name, 0, _MAX_GUESS_RANGE)
            if image_timestamp and image_timestamp < min_:
                min_ = image_timestamp
            if image_timestamp and image_timestamp > max_:
                max_ = image_timestamp

    if Modality.TEXT.name.lower() in modalities:
        timestamps = load_text(scenario_id)['time']
        min_ = min(min_, timestamps.min())
        max_ = max(max_, timestamps.max())

    return int(min(min_, max_)), int(max_)


def _guess_timestamp(name: str, scenario_start: int, scenario_end: int) -> int:
    try:
        file_timestamp = int(name.split('_')[-1])
        if scenario_start < file_timestamp < scenario_end:
            return file_timestamp
    except ValueError:
        pass

    return scenario_start


class ScenarioStorage:
    def __init__(self):
        self._cache = None

    def list_scenarios(self) -> Iterable[str]:
        return tuple(os.path.basename(path[:-1]) for path in glob(os.path.join(_get_base(), "*", "")))

    def load_scenario(self, scenario_id: str) -> Optional[Scenario]:
        scenario_path = _get_path(scenario_id)
        if not os.path.isfile(scenario_path):
            return None

        with open(scenario_path) as json_file:
            json_string = json_file.read()
        scenario = unmarshal(json_string)

        self._cache = ScenarioCache(scenario_id)

        return scenario

    def save_scenario(self, scenario: Scenario) -> None:
        with open(_get_path(scenario.id), 'w') as json_file:
            json_file.write(marshal(scenario))

    def load_modality(self, scenario_id: str, modality: Modality) -> Optional[Iterable[Signal[Any, Any]]]:
        if not self._cache or self._cache.scenario_id != scenario_id:
            self.load_scenario(scenario_id)

        if modality in self._cache:
            return self._cache[modality].values()

        modality_meta_path = _get_path(scenario_id, modality)
        if not os.path.isfile(modality_meta_path):
            return None

        with open(modality_meta_path) as json_file:
            signals = unmarshal(json_file.read())

        self._cache[modality] = signals

        return signals

    def save_signals(self, scenario_id: str, modality: Modality, signals: Iterable[Signal[Any, Any]]):
        self._cache[modality] = signals
        self._save_signals(_get_path(scenario_id, modality), signals)

    def save_signal(self, scenario_id: str, signal: Signal[Any, Any]):
        modality = signal.modality
        self._cache[modality][signal.id] = signal
        self._save_signals(_get_path(scenario_id, modality), self._cache[modality].values())

    def _save_signals(self, path, signals):
        with open(path, 'w') as json_file:
            json_file.write(marshal(signals))