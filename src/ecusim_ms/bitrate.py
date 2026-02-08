"""Bitrate presets and validation."""

BITRATE_PRESETS = [125_000, 250_000, 500_000, 1_000_000]
DEFAULT_BITRATE = 500_000


def validate_bitrate(bps: int) -> int:
    if not isinstance(bps, int):
        raise ValueError("bitrate must be an integer")
    if bps < 10_000 or bps > 2_000_000:
        raise ValueError("bitrate out of allowed range (10000..2000000)")
    return bps
