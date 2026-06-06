from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .aligner import (
    align_canonical_words,
    captions_from_raw_words,
    captions_from_timed_tokens,
    raw_word_segments,
    raw_words_to_debug,
    timing_sources,
    tokens_to_debug,
)
from .config import load_config
from .editor_server import serve_editor
from .io import cache_root, convert_to_wav, read_lyrics, wav_duration_ms, write_json
from .runner import run_whisperx_worker
from .setup_env import configure_venv, default_venv_path, ensure_venv, install_heavy_dependencies
from .text import canonical_tokens_from_lines, flatten_lyrics
from .validate import validate_captions

DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "en"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_BATCH_SIZE = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wisperx-caption-aligner",
        description="Align canonical lyric text to audio using WhisperX word timings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="Create/configure the heavy WhisperX virtualenv.")
    setup.add_argument("--venv-path", type=Path, help="Where to create or reuse the WhisperX virtualenv.")
    setup.add_argument("--skip-install", action="store_true", help="Save config without installing dependencies.")

    align = subparsers.add_parser("align", help="Align lyrics to audio and write Remotion Caption[] JSON.")
    align.add_argument("--audio", type=Path, required=True, help="Audio file to align.")
    align.add_argument("--lyrics", type=Path, required=True, help="Canonical lyrics text file.")
    align.add_argument("--out-dir", type=Path, required=True, help="Directory for output JSON files.")
    align.add_argument("--prefix", required=True, help="Output file prefix.")
    align.add_argument("--canonical", action="store_true", help="Write canonical lyric-aligned captions.")
    align.add_argument("--raw", action="store_true", help="Write raw WhisperX transcript captions.")
    align.add_argument("--model", default=DEFAULT_MODEL, help=f"WhisperX ASR model. Default: {DEFAULT_MODEL}.")
    align.add_argument("--language", default=DEFAULT_LANGUAGE, help=f"Language code. Default: {DEFAULT_LANGUAGE}.")
    align.add_argument("--device", default=DEFAULT_DEVICE, help=f"WhisperX device. Default: {DEFAULT_DEVICE}.")
    align.add_argument(
        "--compute-type",
        default=DEFAULT_COMPUTE_TYPE,
        help=f"WhisperX compute type. Default: {DEFAULT_COMPUTE_TYPE}.",
    )
    align.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"WhisperX batch size. Default: {DEFAULT_BATCH_SIZE}.",
    )
    align.add_argument("--venv-path", type=Path, help="Override configured WhisperX virtualenv path.")
    align.add_argument("--cache-dir", type=Path, help="Working cache directory for WAV and WhisperX JSON.")

    editor = subparsers.add_parser("editor", help="Open a visual audio/caption timeline editor.")
    editor.add_argument("--audio", type=Path, required=True, help="Audio file to play while editing.")
    editor.add_argument("--captions", type=Path, required=True, help="Caption JSON to load.")
    editor.add_argument(
        "--out",
        type=Path,
        help="Where edited captions are saved. Defaults to overwriting --captions.",
    )
    editor.add_argument("--host", default="127.0.0.1", help="Host for the local editor server.")
    editor.add_argument("--port", type=int, default=8765, help="Port for the local editor server. Use 0 for any port.")
    editor.add_argument("--no-open", action="store_true", help="Print the URL instead of opening a browser.")

    return parser


def prompt_venv_path() -> Path:
    default = default_venv_path()
    response = input(f"Where should the WhisperX virtualenv be saved? [{default}]: ").strip()
    return Path(response).expanduser() if response else default


def setup_command(args: argparse.Namespace) -> int:
    venv_path = args.venv_path.expanduser() if args.venv_path else prompt_venv_path()
    venv_path = venv_path.resolve()

    print(f"Configuring WhisperX virtualenv: {venv_path}")
    ensure_venv(venv_path)
    if args.skip_install:
        print("Skipping dependency install.")
    else:
        install_heavy_dependencies(venv_path)

    config_path = configure_venv(venv_path)
    print(f"Saved config: {config_path}")
    print_cache_notes()
    return 0


def resolve_venv_path(args: argparse.Namespace) -> Path:
    if args.venv_path:
        return args.venv_path.expanduser().resolve()

    config = load_config()
    if config is None:
        raise RuntimeError("No WhisperX virtualenv configured. Run `wisperx-caption-aligner setup` first.")

    return Path(config.venv_path).expanduser().resolve()


def selected_outputs(args: argparse.Namespace) -> tuple[bool, bool]:
    if not args.canonical and not args.raw:
        return True, True
    return args.canonical, args.raw


def align_command(args: argparse.Namespace) -> int:
    audio_path = args.audio.expanduser().resolve()
    lyrics_path = args.lyrics.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    cache_dir = (args.cache_dir.expanduser().resolve() if args.cache_dir else cache_root().resolve())
    venv_path = resolve_venv_path(args)
    write_canonical, write_raw = selected_outputs(args)

    if not audio_path.exists():
        raise FileNotFoundError(f"Missing audio: {audio_path}")

    lines = read_lyrics(lyrics_path)
    canonical = canonical_tokens_from_lines(lines)
    if not canonical:
        raise ValueError("Lyrics file did not contain any words.")

    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    wav_path = cache_dir / f"{args.prefix}.16k.wav"
    whisperx_result_path = cache_dir / f"{args.prefix}.whisperx.json"

    print(f"Converting audio -> {wav_path}")
    convert_to_wav(audio_path, wav_path)
    max_duration_ms = wav_duration_ms(wav_path)
    prompt = flatten_lyrics(lines)

    run_whisperx_worker(
        venv_path=venv_path,
        audio_wav=wav_path,
        result_path=whisperx_result_path,
        prompt=prompt,
        model=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        batch_size=args.batch_size,
    )

    whisperx_payload = json.loads(whisperx_result_path.read_text())
    aligned_result = whisperx_payload["aligned"]
    raw_words = raw_word_segments(aligned_result, max_duration_ms)
    timed_tokens = align_canonical_words(canonical, raw_words, max_duration_ms)
    canonical_captions = captions_from_timed_tokens(timed_tokens)
    raw_captions = captions_from_raw_words(raw_words)

    if write_canonical:
        errors = validate_captions(
            canonical_captions,
            expected_words=len(canonical),
            max_duration_ms=max_duration_ms,
        )
        if errors:
            raise RuntimeError("\n".join(errors))
        path = out_dir / f"{args.prefix}.captions.json"
        write_json(path, canonical_captions)
        print(f"Wrote canonical captions: {path}")

    if write_raw:
        errors = validate_captions(raw_captions, expected_words=None, max_duration_ms=max_duration_ms)
        if errors:
            raise RuntimeError("\n".join(errors))
        path = out_dir / f"{args.prefix}.raw.captions.json"
        write_json(path, raw_captions)
        print(f"Wrote raw captions: {path}")

    debug_path = out_dir / f"{args.prefix}.debug.json"
    write_json(
        debug_path,
        {
            "model": args.model,
            "language": args.language,
            "device": args.device,
            "computeType": args.compute_type,
            "batchSize": args.batch_size,
            "sourceAudio": str(audio_path),
            "lyrics": str(lyrics_path),
            "wavPath": str(wav_path),
            "whisperxResultPath": str(whisperx_result_path),
            "durationMs": max_duration_ms,
            "rawWordCount": len(raw_words),
            "canonicalWordCount": len(canonical),
            "firstRawWordStartMs": raw_words[0].start_ms if raw_words else None,
            "lastRawWordEndMs": raw_words[-1].end_ms if raw_words else None,
            "timingSources": timing_sources(timed_tokens),
            "segments": whisperx_payload.get("segments", []),
            "rawWords": raw_words_to_debug(raw_words),
            "tokens": tokens_to_debug(timed_tokens),
            "outputs": {
                "canonical": write_canonical,
                "raw": write_raw,
            },
        },
    )
    print(f"Wrote debug report: {debug_path}")
    print_cache_notes()
    return 0


def editor_command(args: argparse.Namespace) -> int:
    captions_path = args.captions.expanduser().resolve()
    output_path = args.out.expanduser().resolve() if args.out else captions_path
    serve_editor(
        audio_path=args.audio,
        captions_path=captions_path,
        output_path=output_path,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )
    return 0


def print_cache_notes() -> None:
    print("\nHeavy/cache locations to know about:")
    print("- Config: ~/.config/wisperx-caption-aligner/config.json")
    print("- Faster Whisper models: ~/.cache/huggingface/hub/")
    print("- WhisperX/Torch aligner models: ~/.cache/torch/")
    print("- Local converted WAV/results: .cache/wisperx-caption-aligner/ or --cache-dir")
    if shutil.which("ffmpeg") is None and shutil.which("afconvert") is None:
        print("- Audio conversion missing: install ffmpeg or run on macOS with afconvert.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "setup":
            return setup_command(args)
        if args.command == "align":
            return align_command(args)
        if args.command == "editor":
            return editor_command(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
