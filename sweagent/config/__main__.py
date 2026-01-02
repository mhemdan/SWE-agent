from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config_loader import ConfigLoader


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate a SWE-Agent configuration file')
    parser.add_argument('--config', required=True, help='Path to the YAML config to validate')
    args = parser.parse_args()

    loader = ConfigLoader()
    try:
        loader.load_config(Path(args.config))
    except Exception as exc:  # noqa: BLE001
        print(f'Config validation failed: {exc}', file=sys.stderr)
        sys.exit(1)
    print(f'Config {args.config} is valid')


if __name__ == '__main__':
    main()
