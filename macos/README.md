# Launching JARVIS without Terminal, and a global keyboard shortcut

This folder has a minimal `JARVIS.app` — no compiled code, just an
`Info.plist` and a shell script that activates the project's virtual
environment and runs `jarvis --ui`. Double-clicking it (or triggering it
via a keyboard shortcut) opens the HUD directly, no Terminal window.

## 1. Install the app

```bash
cp -r macos/JARVIS.app /Applications/
```

The first time you open it, macOS Gatekeeper will refuse to run an
unsigned app from a double-click. Instead: **right-click `JARVIS.app` in
Finder → Open → Open** (only needed once).

If your JARVIS project isn't at `~/JARVIS`, either:
- right-click `JARVIS.app` → **Show Package Contents** → edit
  `Contents/MacOS/JARVIS` and change the `JARVIS_DIR` default, or
- set an environment variable named `JARVIS_PROJECT_DIR` (e.g. in a
  LaunchAgent's environment, or globally via `launchctl setenv`).

Launching it again while JARVIS is already running brings the existing
window to the front instead of opening a second copy — that's what makes
a keyboard shortcut behave like a toggle rather than spawning duplicates.

If something goes wrong on launch (no visible window, no error dialog),
check `~/.jarvis/logs/launcher.log` and `~/.jarvis/logs/jarvis.log`.

## 2. Give it a global keyboard shortcut

macOS has no built-in "assign a hotkey to launch any app" panel, but
**Automator Quick Actions (Services)** can be given one, and Services work
from anywhere regardless of which app is focused:

1. Open **Automator** (Spotlight → "Automator").
2. **File → New → Quick Action**.
3. At the top, set **"Workflow receives"**: `no input`, in **any
   application**.
4. Search the actions list for **"Run Shell Script"** and drag it into
   the workflow.
5. Set **Shell**: `/bin/bash`, and enter:
   ```bash
   open -a /Applications/JARVIS.app
   ```
6. **File → Save**, name it something like `Activate JARVIS`.
7. Open **System Settings → Keyboard → Keyboard Shortcuts → Services**.
8. Find **"Activate JARVIS"** under General, click the shortcut field on
   the right, and press the key combo you want (e.g. `⌃⌥Space`  — avoid
   combos already used by Spotlight, Siri, or other apps).

Press that combo from anywhere — JARVIS opens, or comes to the front if
it's already running.

### Alternative: Shortcuts.app

On recent macOS you can do the same thing in **Shortcuts.app** instead of
Automator: new shortcut → add a **"Run Shell Script"** action with the
same `open -a /Applications/JARVIS.app` command → in the shortcut's
Details pane, enable it as a **Quick Action** available in Services, then
assign the keyboard shortcut the same way via System Settings.

### If you want fancier hotkey behavior

The Services approach above only supports a plain key combo assigned
per-service. If you want things like a press-and-hold push-to-talk key
or per-app contextual behavior, that needs a dedicated hotkey daemon —
[Hammerspoon](https://www.hammerspoon.org/) (free, scriptable in Lua) is
the most common choice, or `skhd` (a lightweight hotkey daemon, usually
installed via Homebrew: `brew install skhd`) if you just want simple
global bindings without writing Lua. Both are separate installs, not
covered here.
