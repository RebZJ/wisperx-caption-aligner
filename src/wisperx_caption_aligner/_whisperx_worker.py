from __future__ import annotations

import json
import sys
import warnings
import wave
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    message=r"\s*torchcodec is not installed correctly[\s\S]*",
    category=UserWarning,
)

import numpy as np
import whisperx


def load_wav_float(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sample_rate != 16_000:
        raise ValueError(f"Expected a 16k WAV for WhisperX, got {sample_rate}Hz")
    if sample_width != 2:
        raise ValueError(f"Expected 16-bit PCM WAV, got {sample_width}-byte samples")

    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1).astype(np.float32)

    return data


def run(payload: dict[str, Any]) -> None:
    audio = load_wav_float(Path(payload["audio_wav"]))
    device = payload["device"]
    language = payload["language"]

    print(f"Loaded audio: {len(audio) / 16000:.3f}s")
    print(f"Running WhisperX model={payload['model']} device={device}")
    model = whisperx.load_model(
        payload["model"],
        device,
        compute_type=payload["compute_type"],
        language=language,
        vad_method="silero",
        asr_options={"initial_prompt": payload["prompt"]},
    )
    result = model.transcribe(
        audio,
        batch_size=int(payload["batch_size"]),
        language=language,
        print_progress=True,
    )

    print("Loading WhisperX phoneme aligner")
    align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
    aligned_result = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
        print_progress=True,
    )

    output = {
        "segments": result.get("segments", []),
        "aligned": aligned_result,
    }
    result_path = Path(payload["result_path"])
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    run(json.loads(sys.argv[1]))
