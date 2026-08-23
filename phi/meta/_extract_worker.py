# -*- coding: utf-8 -*-
"""Single-track extraction worker — spawned by batch_extractor via subprocess.

Usage: python _extract_worker.py <audio_path> <output_json_path>

Writes JSON result to output_json_path (temp file) instead of stdout so that
pipe inheritance by ffmpeg/audioread subprocesses never blocks the parent.
Avoids importing phi.meta.__init__ to prevent tkinter/pygame initialisation.
"""
import importlib.util, json, sys
from pathlib import Path


def _load_extractor():
    spec = importlib.util.spec_from_file_location(
        "_batch_extractor_standalone",
        Path(__file__).parent / "batch_extractor.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._extract_one


if __name__ == "__main__":
    audio_path  = sys.argv[1]
    output_path = sys.argv[2]

    _extract_one = _load_extractor()
    result = _extract_one(audio_path)

    Path(output_path).write_text(json.dumps(result))
