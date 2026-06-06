from wisperx_caption_aligner.cli import build_parser, selected_outputs


def parse(args: list[str]):
    return build_parser().parse_args(args)


def test_output_modes_default_to_both() -> None:
    args = parse(["align", "--audio", "a.mp3", "--lyrics", "l.txt", "--out-dir", "out", "--prefix", "song"])
    assert selected_outputs(args) == (True, True)


def test_output_modes_canonical_only() -> None:
    args = parse(
        ["align", "--audio", "a.mp3", "--lyrics", "l.txt", "--out-dir", "out", "--prefix", "song", "--canonical"]
    )
    assert selected_outputs(args) == (True, False)


def test_output_modes_raw_only() -> None:
    args = parse(["align", "--audio", "a.mp3", "--lyrics", "l.txt", "--out-dir", "out", "--prefix", "song", "--raw"])
    assert selected_outputs(args) == (False, True)


def test_editor_defaults_to_overwriting_loaded_captions() -> None:
    args = parse(["editor", "--audio", "a.mp3", "--captions", "song.captions.json", "--no-open"])
    assert args.command == "editor"
    assert args.out is None
