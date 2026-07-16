#!/usr/bin/env python3
"""Apply local tweaks to an installed Spektrafilm data pack.

The exporter (spektrafilm_export_data.py) regenerates the pack verbatim from
the upstream spektrafilm release, so every local adjustment lives here and the
script must be re-run after each pack regeneration:

    python tools/spektrafilm_pack_tweaks.py            # default config dir
    python tools/spektrafilm_pack_tweaks.py -d <dir>   # explicit pack dir

Tweaks applied (all idempotent — targets are absolute, not multipliers):

1. Grain recalibration (cine + Verita stocks). Upstream copies Kodak's
   cine-datasheet rms-granularity verbatim (e.g. Vision3 500T [9, 13, 30]),
   but the consumer still stocks use hand-tuned values on a much flatter
   scale (Gold 200 [5, 5, 5], Portra 160 [3.5]). Mixed together, Vision3 50D
   renders grainier than Gold 200 — inverted from reality, where 50D is far
   finer. The cine measurement basis (ECN-2, status M, per-record) is not
   comparable to the still-stock scale, so the values below are the upstream
   per-channel figures halved: this keeps each stock's channel character and
   the 50D < Verita < 200T < 250D < 500T ordering while landing the family
   sensibly on the still-stock ladder (portra_160 3.5 / ektar 4 / portra_400
   4.5 / gold 5 / portra_800 6).

2. CineStill 800T profile. Kodak Vision3 500T with the remjet antihalation
   backing removed: identical spectral data, halation switched to upstream's
   (use='cine', antihalation='no') preset — strength (0.30, 0.10, 0.015)
   with the blue component zeroed (the film base and red-sensitive layer
   absorb blue on back-reflection; keeps the halo red/orange instead of
   whitening it), first bounce sigma 50 um. Derived after the grain rescale
   so it inherits the recalibrated 500T grain. The stock is also cloned into
   every neutral_print_filters table (same spectra as 500T -> same neutral
   CMY filtration); without those entries darktable silently falls back to
   generic filtration and the render takes a strong green cast.
"""

import argparse
import copy
import json
import os
import sys

# upstream cine-datasheet values halved (see module docstring, tweak 1)
GRAIN_RESCALE = {
    "kodak_verita_200d":  [3.0, 4.0, 5.0],    # was [6, 8, 10]
    "kodak_vision3_50d":  [3.5, 3.5, 6.0],    # was [7, 7, 12]
    "kodak_vision3_200t": [3.5, 4.0, 8.5],    # was [7, 8, 17]
    "kodak_vision3_250d": [5.0, 5.5, 9.0],    # was [10, 11, 18]
    "kodak_vision3_500t": [4.5, 6.5, 15.0],   # was [9, 13, 30]
}

STOCK_SRC = "kodak_vision3_500t"
STOCK_DST = "cinestill_800t"
DISPLAY_NAME = "CineStill 800T"
# upstream _HALATION_PRESETS[('cine', 'no')] — rem-jet removed — with the
# blue component zeroed for a red/orange halo (tune here if it reads too
# white: lower the green term, e.g. 0.10 -> 0.06)
HALATION_STRENGTH = [0.30, 0.10, 0.0]
HALATION_SIGMA_UM = [50.0, 50.0, 50.0]


def default_dir() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.config"))
    return os.path.join(base, "darktable", "spektrafilm")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--dir", default=default_dir(),
                    help="spektrafilm data pack directory (default: %(default)s)")
    args = ap.parse_args()

    pack_path = os.path.join(args.dir, "pack.json")
    src_prof = os.path.join(args.dir, "profiles", f"{STOCK_SRC}.json")
    dst_prof = os.path.join(args.dir, "profiles", f"{STOCK_DST}.json")
    for p in (pack_path, src_prof):
        if not os.path.exists(p):
            print(f"error: {p} not found — is the data pack installed?", file=sys.stderr)
            return 1

    with open(pack_path, encoding="utf-8") as f:
        pack = json.load(f)
    defaults = pack.setdefault("film_render_defaults", {})

    # 1. grain recalibration
    for stock, rms in GRAIN_RESCALE.items():
        entry = defaults.get(stock)
        if not entry or "grain" not in entry:
            print(f"warning: no grain entry for {stock}, skipped", file=sys.stderr)
            continue
        entry["grain"]["rms_granularity"] = rms
        print(f"grain    {stock}: rms_granularity -> {rms}")

    # 2. CineStill 800T profile (verbatim 500T spectra, retagged remjet-removed)
    with open(src_prof, encoding="utf-8") as f:
        prof = json.load(f)
    prof["info"]["stock"] = STOCK_DST
    prof["info"]["name"] = DISPLAY_NAME
    prof["info"]["antihalation"] = "no"
    with open(dst_prof, "w", encoding="utf-8") as f:
        json.dump(prof, f)
    print(f"profile  wrote {dst_prof}")

    if STOCK_SRC not in defaults:
        print(f"error: film_render_defaults.{STOCK_SRC} missing from pack.json",
              file=sys.stderr)
        return 1
    entry = copy.deepcopy(defaults[STOCK_SRC])  # after rescale: inherits new grain
    entry.setdefault("halation", {})
    entry["halation"]["strength"] = HALATION_STRENGTH
    entry["halation"]["first_sigma_um"] = HALATION_SIGMA_UM
    defaults[STOCK_DST] = entry
    print(f"defaults {STOCK_DST}: halation strength {HALATION_STRENGTH}, "
          f"sigma {HALATION_SIGMA_UM[0]} um, grain {entry['grain']['rms_granularity']}")

    # clone the source stock's neutral enlarger filtration for every paper and
    # illuminant (identical spectra -> identical neutral CMY). Without these,
    # darktable's neutral-filter lookup silently falls back to generic values
    # and the print render takes a strong green cast.
    npf = pack.get("neutral_print_filters", {})
    n_cloned = 0
    for paper, by_ill in npf.items():
        for ill, by_film in by_ill.items():
            if STOCK_SRC in by_film:
                by_film[STOCK_DST] = copy.deepcopy(by_film[STOCK_SRC])
                n_cloned += 1
    print(f"neutrals {STOCK_DST}: cloned {STOCK_SRC} filtration in {n_cloned} "
          f"paper/illuminant tables")

    with open(pack_path, "w", encoding="utf-8") as f:
        json.dump(pack, f)
    print(f"updated  {pack_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
