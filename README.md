# NoHatsModGUI

A Windows GUI for building config files for [nhcustom2](https://pevhs.ch/tf2/nhcustom2/), the TF2 no-hats-mod customizer.

> **DISCLAIMER:** the program was built using Claude.

## Features

- Every cosmetic from nhcustom2's database, grouped by update in release order, then by class, then alphabetically
- Collapsible update sections with a checkbox that selects the whole section
- Search by cosmetic name as you type
- Keep or remove the selected cosmetics
- Saves `config.txt` for nhcustom2 and can run nhcustom2 directly

## Setup

1. Put `NoHatsModGUI.exe` in a folder.
2. Put the `nhcustom2_windows` folder (from [pevhs.ch/tf2/nhcustom2/](https://pevhs.ch/tf2/nhcustom2/)) in the same folder.
3. Put the latest [database.csv](https://pevhs.ch/tf2/nhcustom2/database.csv) inside `nhcustom2_windows`.
4. To run nhcustom2, put `no_hats_bgum.vpk` in `nhcustom2_windows/input`. Clicking **Run nhcustom2** decompiles it there (deleting the `.vpk`), runs nhcustom2, then moves the result into `output/no-hats-bgum-custom` and packs it as `output/no-hats-bgum-custom.vpk`. An already-decompiled mod (`input/models`) works too.

TF2's `vpk.exe` isn't needed: it currently extracts VPKs as empty folders, so NoHatsModGUI reads the VPK itself.

## Building

Requires Python 3.13 on Windows.

```powershell
.\build.ps1
```

The exe is written to `dist\NoHatsModGUI.exe`.
