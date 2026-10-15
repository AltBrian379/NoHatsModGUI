# NoHatsModGUI

A Windows GUI for building config files for [nhcustom2](https://pevhs.ch/tf2/nhcustom2/), the TF2 no-hats-mod customizer.

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
4. To run nhcustom2, put a decompiled no-hats-bgum mod in `nhcustom2_windows/input`.

## Building

Requires Python 3.13 on Windows.

```powershell
.\build.ps1
```

The exe is written to `dist\NoHatsModGUI.exe`.
