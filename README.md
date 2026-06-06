# wisperx-caption-aligner

A lightweight CLI for aligning canonical lyrics to audio using WhisperX word timings.

It writes Remotion-compatible `Caption[]` JSON, while keeping the heavy WhisperX/Torch install out of the package itself. Install the CLI quickly, then run an explicit setup step when you are ready to create the heavy WhisperX virtualenv.

> The repo name intentionally follows the requested spelling: `wisperx-caption-aligner`.

## What it does

- Transcribes and force-aligns audio with WhisperX.
- Preserves your supplied lyrics as canonical display text.
- Writes raw WhisperX transcript captions for debugging.
- Writes canonical lyric-aligned captions for karaoke/lyric video workflows.
- Writes a debug report with raw words, matched tokens, interpolation sources, and paths.
- Uses macOS `afconvert` for audio conversion when available, otherwise uses `ffmpeg`.

## Install

From GitHub:

```bash
pipx install git+https://github.com/RebZJ/wisperx-caption-aligner.git
```

Or with pip:

```bash
pip install git+https://github.com/RebZJ/wisperx-caption-aligner.git
```

For local development:

```bash
git clone https://github.com/RebZJ/wisperx-caption-aligner.git
cd wisperx-caption-aligner
python -m pip install -e ".[dev]"
```

## Setup heavy WhisperX dependencies

The package does **not** install WhisperX/Torch by default. Run setup once:

```bash
wisperx-caption-aligner setup
```

If `--venv-path` is omitted, the CLI asks where to save the heavy virtualenv:

```bash
wisperx-caption-aligner setup --venv-path ~/.local/share/wisperx-caption-aligner/.venv-whisperx
```

The setup command:

- creates or reuses the selected virtualenv,
- installs `whisperx` and `numpy` inside it,
- stores the path at `~/.config/wisperx-caption-aligner/config.json`,
- prints model/cache locations so you can clean them manually later.

## Align lyrics

```bash
wisperx-caption-aligner align \
  --audio song.mp3 \
  --lyrics lyrics.txt \
  --out-dir alignments \
  --prefix song
```

If neither `--canonical` nor `--raw` is selected, both are written:

```text
alignments/song.captions.json
alignments/song.raw.captions.json
alignments/song.debug.json
```

Choose one output mode:

```bash
wisperx-caption-aligner align --audio song.mp3 --lyrics lyrics.txt --out-dir alignments --prefix song --canonical
wisperx-caption-aligner align --audio song.mp3 --lyrics lyrics.txt --out-dir alignments --prefix song --raw
```

## Defaults

- WhisperX model: `small`
- Language: `en`
- Device: `cpu`
- Compute type: `int8`
- Batch size: `4`
- Initial prompt: your lyrics flattened into one line

Override them:

```bash
wisperx-caption-aligner align \
  --audio song.mp3 \
  --lyrics lyrics.txt \
  --out-dir alignments \
  --prefix song \
  --model medium \
  --device cpu \
  --compute-type int8 \
  --batch-size 4
```

## Output format

Caption JSON matches Remotion's `Caption[]` shape:

```json
[
  {
    "text": "I’ve",
    "startMs": 2007,
    "endMs": 2167,
    "timestampMs": 2007,
    "confidence": 0.74
  }
]
```

Canonical captions keep your lyric words exactly as written. Raw captions use WhisperX's transcription words.

## Cache locations

The tool never deletes caches automatically.

Common locations:

- CLI config: `~/.config/wisperx-caption-aligner/config.json`
- Heavy virtualenv: the path you selected during `setup`
- Faster Whisper models: `~/.cache/huggingface/hub/`
- WhisperX/Torch aligner models: `~/.cache/torch/`
- Temporary WAV/WhisperX JSON: `.cache/wisperx-caption-aligner/` or your `--cache-dir`

## Development

```bash
python -m pip install -e ".[dev]"
pytest
wisperx-caption-aligner --help
wisperx-caption-aligner setup --help
wisperx-caption-aligner align --help
```

CI runs lightweight unit tests only. It does not download or run WhisperX models.
