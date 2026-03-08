# Merged update notes

Latest development branch with Caleb's updates**.

## What was changed
- Added `json_files/settings.json` and converted `settings.py` to load/save from JSON.
- Moved your current Discord runtime into `main_program.py`.
- Replaced `main.py` with a launcher/settings editor GUI that starts `main_program.py`.
- Added an `assets/` tree that mirrors your icon folders.
- Added a `source/` package layout with compatibility wrappers pointing at your current modules, so Caleb-style imports can coexist with your existing code.
- Added Caleb's `source/discord_commands`, `source/join_sim`, colour-check utilities, OCR helper, `source/ASA/inventories/structures.py`, and dedi/crop/forge helper modules.
- Added `json_files/dedis.json`.
- Updated `requirements.txt` to include `pygetwindow` and `pytesseract`.

## Important behavior choice
Your **current runtime logic remains the authoritative path**:
- `main_program.py`
- root `bot/`, `ASA/`, `logs/`, `crafting/`, and utility modules

The new `source/` tree is staged for migration and compatibility, not yet a full switchover.

## High-value next manual merges
1. Port useful pieces from Caleb's reconnect flow into your existing reconnect path.
2. Decide whether to adopt the modular slash-command runtime or keep your current runtime.
3. Wire dedi support into your deposit/station logic only after validating your station JSON formats.
4. Cherry-pick only the safe helper logic from Caleb's structure modules; several are experimental.

## Known caveats
- Caleb's render tek pod buff bug is still present in his structure branch unless you patch it manually.
- `source/gacha_bot/structures/forge.py`, `replicatior.py`, `tek_cropplots.py`, and some crafting helpers are included for reference, not guaranteed production-ready.
- `source/join_sim` was added as a parallel reconnect system and is not yet connected into your current reconnect flow.
