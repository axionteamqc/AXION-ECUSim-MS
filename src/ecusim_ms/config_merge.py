"""Merge CLI args with control.json config."""

from __future__ import annotations

from dataclasses import replace

from ecusim_ms.models import ControlConfig


def merge_control_with_args(control_cfg: ControlConfig, args) -> ControlConfig:
    """Return a new ControlConfig with CLI args overriding control fields."""
    cfg = control_cfg
    cfg = replace(
        cfg,
        backend=args.backend if getattr(args, "backend", None) is not None else cfg.backend,
        iface=args.iface if args.iface is not None else cfg.iface,
        channel=args.channel if args.channel is not None else cfg.channel,
        port=args.port if getattr(args, "port", None) is not None else cfg.port,
        serial_baud=(
            args.serial_baud if getattr(args, "serial_baud", None) is not None else cfg.serial_baud
        ),
        skip_bitrate=(
            args.skip_bitrate
            if getattr(args, "skip_bitrate", None) is not None
            else cfg.skip_bitrate
        ),
        bitrate=args.bitrate if args.bitrate is not None else cfg.bitrate,
        hz=args.hz if args.hz is not None else cfg.hz,
        mode=args.mode if args.mode is not None else cfg.mode,
    )
    return cfg
