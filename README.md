# Nightreign auto-timer

<img src="assets/nightreign-auto-timer.png" width="96" alt="Nightreign auto-timer icon">

Automatic day and storm timer for Elden Ring Nightreign on Windows. A desktop window and a transparent overlay follow the game using local save files and window metadata. The app does not require Overwolf or a mod loader and does not read game-process memory or inject code.

## Windows executable

Run **Nightreign auto-timer.exe**. Python, a mod loader and additional asset files are not needed. You can move the executable into your preferred writable folder.

The app reads **settings.json next to the executable** and creates it immediately on first launch if it is missing. Keep that JSON beside the executable when moving the app to preserve your preferences. Launching from another working directory or a shortcut does not change the settings location. Normal use creates no other files beside the executable.

## Run from source

Use Windows 10/11 and 64-bit Python 3.12 or newer with Tkinter. In the project folder:

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Double-click **Launch Nightreign Timer.cmd** before leaving the Bastion, or run:

~~~powershell
.venv\Scripts\pythonw.exe app.py
~~~

The source launcher prefers a built executable in dist, then the local virtual environment, then Python on PATH or the Windows Python launcher. Closing the desktop window exits the timer; the optional automatic-opening watcher is separate.

## Automatic opening and closing

The desktop window has two independent checkboxes, both off by default:

- **Open automatically with Nightreign** starts a hidden watcher immediately and adds it to the current user's Windows startup. It opens one timer window when Nightreign appears. Closing the timer manually keeps it closed for the rest of that game session; the next launch of Nightreign can open it again. Unchecking the option removes Windows startup and stops the watcher.
- **Close automatically with Nightreign** closes the timer as soon as the previously detected game window disappears (normally within a fraction of a second). Minimizing the game or switching to another app does not trigger it. This option works independently of automatic opening.

Closing the timer window always closes the timer itself. If automatic opening is enabled, the separate watcher remains in the background. Keep the executable in place while this option is enabled; if you move it, open the app once from its new location to update Windows startup. No administrator rights are required.

## Overlay controls

Press **F10** to edit the overlay in place. The preview displays **Edit / 0:00**.

- Drag the text or its background using the four-arrow cursor.
- **Reset** aligns the HUD with the top of the game client area.
- **Hide / Show** immediately affects the text and background; editing controls stay visible.
- The opacity slider starts at **50%** and affects only the background.
- **Outline: Off / On** toggles the outline around both timer lines immediately. It starts off and is saved with your preferences.
- **Done** or F10 closes editing. Outside editing, clicks pass through the overlay.

The compact HUD uses native-resolution text and soft left/right background edges. Text and geometry update only when their visible state changes; the game window is still checked every 50 ms for responsive tracking. Editing controls have outlined text for readability over bright scenes. Position, opacity, visibility and the shortcut are saved when changed and restored on the next launch.

## Settings and local data

Preferences are stored in **settings.json** beside the executable (or app.py when running from source) and are excluded from Git. The file is created automatically at startup; **settings.example.json** documents the user-facing options. Close the app before editing settings manually.

~~~json
{
  "source": "",
  "edit_hotkey": "F10",
  "overlay_font": 34,
  "overlay_background_opacity": 0.5,
  "overlay_hidden": false,
  "overlay_outline": false,
  "overlay_anchor_x": 0.5,
  "overlay_anchor_y": 0.0,
  "overlay_x": null,
  "overlay_y": null,
  "open_with_game": false,
  "close_with_game": false
}
~~~

An empty source enables automatic discovery of NR0000.sl2 and NR_TimerTests.sl2 under %APPDATA%\Nightreign; the detected path is kept in memory. A custom source can be set locally; a freshly updated game save can still be detected automatically. The first character slot is read, and save files are opened for reading only.

Save entries are read and validated one at a time to limit temporary allocations. All 14 encrypted entries retain padding and checksum validation, and clock detection still rejects ambiguous layouts.

Only user preferences are saved. Position values are managed by the overlay editor: anchors are relative to the game window, while x/y preserve the fallback desktop position. Calibrated phase times and automatic detection are defined in code; old internal options are ignored and removed when preferences are saved. When enabled, the timer outline adapts to screen DPI. Editing controls keep their own outline for readability.

Shortcut examples include F9, Ctrl+E and Ctrl+Alt+F10. F1–F24, A–Z, 0–9 and common navigation keys are supported, with optional Ctrl, Alt and Shift. Invalid values fall back to F10; the desktop hint reports conflicts with another app.

Only the executable and **settings.json** are needed in the app folder. Instance coordination uses tiny lock files in the Windows temporary folder. Troubleshooting data is off by default; launch with **--diagnostics** to write logs and runtime state in a **.diagnostics/** subfolder. The application does not record or copy game saves.

## Detection and limits

Day 1 starts from the saved morning departure. The evening-to-morning reset identifies Day 2. Recognized final-area locations identify Day 3, and a saved Bastion location returns the timer to **Waiting for expedition...**. The overlay is hidden during Day 3 and outside an expedition.

Both days use the same calibrated schedule:

| Transition | Time from day start |
| --- | --- |
| First closing starts | 04:31.75 |
| First closing ends | 07:32.10 |
| Second closing starts | 11:02.10 |
| Second closing ends | 13:59.20 |

Detection follows the game's save writes. A return to the Bastion can remain undetected until the next write; opening and closing the in-game menu triggered an update in local testing. Repeated fresh saves with an empty location and frozen playtime suspend the timer for an observed exit pattern, but this heuristic does not cover every title-screen exit. Timing between checkpoints remains an estimate.

Windowed and borderless modes are supported. Actual HDR appearance and exclusive fullscreen visibility remain unverified. An optional browser view at **http://127.0.0.1:17333/** can be used with Edge in Windows Game Bar; the local server serves only the timer page and its sanitized state.

## Project structure

| File | Responsibility |
| --- | --- |
| app.py | Desktop UI, save watcher and application lifecycle |
| engine.py | Automatic day transitions and session suspension |
| save_reader.py | Read-only save validation and observation parsing |
| timings.py | Phase schedule, labels and countdown colors |
| overlay.py | In-place editor and game-following HUD |
| layered_background.py | Transparent background with soft side edges |
| game_window.py | Window bounds and DPI metadata |
| hotkeys.py | Configurable shortcut parsing |
| desktop_controls.py | DPI-aware desktop checkboxes |
| lifecycle.py | Automatic opening/closing, Windows startup and instance coordination |
| gamebar_view.py / gamebar.html | Optional local browser view |
| tests/ | Portable unit tests, synthetic fixtures and GUI smoke check |

## Build the executable

On Windows, using the development virtual environment:

~~~powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build_exe.py
~~~

The output is **dist/Nightreign auto-timer.exe**, a single file with Python, Tk, cryptography, the icon and the browser view bundled inside. Personal settings and game saves are never included. The build also creates **dist/Nightreign-auto-timer.zip** with the executable and clean default settings for Nexus. Both automatic options are off in that package. Build outputs are ignored by Git.

## Development and validation

~~~powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe app.py --self-test
~~~

Tests generate synthetic save containers in temporary directories. No player saves, account identifiers, captures or machine-specific paths are needed. The Windows GUI smoke check operates only on its own windows.

Save-format reference: [er-save-manager](https://github.com/Hapfel1/er-save-manager/blob/main/src/er_save_manager/games/NR/parser.py). Map reference: [Nightreign map names](https://soulsmodding.com/doku.php?id=nr-refmat:map-name-list).
