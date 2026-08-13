# Flet Packaging (`flet build`)

## What this is
`flet build` compiles the Flet UI into a native, distributable app —
not something achievable with `pip install` alone. It downloads a
Flutter SDK and its engine artifacts, then runs a real Flutter/Dart
build (per target platform) around the Python app.

## Two separate entry points, two separate builds
`flet_run.py` (the dev entry point) picks a persona via `--persona
nova|lyra`, but a packaged native app has no CLI args to pass the way a
locally-run script does. Rather than build one package that guesses or
needs an in-app selector, each persona gets its own dedicated entry
point and its own separate build:

- `nova_main.py` — packages Nova only
- `lyra_main.py` — packages Lyra only

Both just reuse the same `AssistantCore` + `create_<persona>_app` +
automation-ticker wiring `flet_run.py` already established (Milestone
13's tick-wiring decision) — no new app logic, just an argument-free
`main()` per persona so `flet build` has an unambiguous entry point.

## Build commands
Run these from the repo root, on a machine with normal internet access
(see "Why this couldn't be finished here" below for why that matters).
`flet build` will auto-install the Flutter SDK on first run if it's not
already present — expect that first build to take a while and download
several hundred MB.

```bash
# Linux
flet build linux --module-name nova_main \
  --project "eclipsis-ai-nova" --product "ECLIPSIS-AI Nova" \
  --org "com.eclipsisai" --description "ECLIPSIS-AI personal assistant (Nova persona)"

flet build linux --module-name lyra_main \
  --project "eclipsis-ai-lyra" --product "ECLIPSIS-AI Lyra" \
  --org "com.eclipsisai" --description "ECLIPSIS-AI personal assistant (Lyra persona)"

# macOS (run on a Mac; needs Xcode command-line tools)
flet build macos --module-name nova_main --project "eclipsis-ai-nova" \
  --product "ECLIPSIS-AI Nova" --org "com.eclipsisai"
flet build macos --module-name lyra_main --project "eclipsis-ai-lyra" \
  --product "ECLIPSIS-AI Lyra" --org "com.eclipsisai"

# Windows (run on Windows; needs Visual Studio Build Tools with the
# "Desktop development with C++" workload)
flet build windows --module-name nova_main --project "eclipsis-ai-nova" ^
  --product "ECLIPSIS-AI Nova" --org "com.eclipsisai"
flet build windows --module-name lyra_main --project "eclipsis-ai-lyra" ^
  --product "ECLIPSIS-AI Lyra" --org "com.eclipsisai"
```

Output lands in `build/<platform>/` (e.g. `build/linux/`,
`build/macos/`, `build/windows/`) — a runnable app bundle/executable
per platform, one directory per build you ran.

Swap `linux` for `web` if you want a browser-deployable build instead
of (or in addition to) a native one — same `--module-name` flags apply;
`ft.run(target)` in both entry points works for either since `flet_run.py`
already established that `ft.run` (not the `--web`-flag branch, which is
dev-only) is what a packaged/served app uses.

## Prerequisites per platform
- **Linux**: `clang`, `cmake`, `ninja-build`, `pkg-config`,
  `libgtk-3-dev` — `flet doctor` after installing Flutter will tell you
  what's missing (run `~/flutter/<version>/bin/flutter doctor` if
  `flet`'s own `flet doctor` doesn't surface it).
- **macOS**: Xcode + command-line tools (`xcode-select --install`).
- **Windows**: Visual Studio 2022 Build Tools, "Desktop development
  with C++" workload.
- **Android/iOS**: not attempted or documented here — this pass only
  covers the two desktop-adjacent targets (Nova/Lyra are desktop apps
  per their window-geometry-restore and mic/camera permission model);
  revisit if mobile packaging is actually wanted later.

## Why this couldn't be finished in this session
Verified directly rather than assumed, twice now — most recently on
2026-08-13: `flet build linux` was run in the sandbox this work
happened in. It got all the way through argument parsing, target
validation, and project initialization — confirming
`nova_main.py`/`lyra_main.py` and the command-line flags above are
correctly configured — before failing at Flutter SDK acquisition
(`storage.googleapis.com`, `HTTP 403`). Checking directly: the
sandbox's egress proxy returns `x-deny-reason: host_not_allowed` for
that host — a network-egress allowlist, not a transient failure or an
app config problem.

Manually seeding the Flutter SDK via `git clone` from GitHub (which
*is* reachable) got one step further, past SDK acquisition — but
`flutter precache --linux` then needs the engine artifacts (Dart SDK,
native binaries) from the same `storage.googleapis.com`-hosted CDN and
hit the identical wall (a truncated/corrupt-looking download rather
than a clean HTTP error this time, but the same `host_not_allowed`
proxy response underneath). Both attempts confirm this is a
sandbox-specific network-egress restriction that would not affect a
normal developer machine with regular internet access — `storage.
googleapis.com` isn't an unusual or blocked host in general, just not
on this environment's allowlist.

## Icons / branding
No custom icon or splash screen has been configured yet — `flet build`
will use its own default Flet icon. `--project`/`--product`/`--org`/
`--description` above at least set the app metadata (window title,
executable name, bundle identifier). Custom icons are configured by
placing images in an `assets/` folder and pointing `--icon-*`/
`--splash-*` build flags at them — worth a follow-up if branding
matters before shipping to anyone outside internal testing.
