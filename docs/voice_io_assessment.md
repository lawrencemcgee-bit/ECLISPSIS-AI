# Real Voice I/O — Assessment & Setup

Post-roadmap work (not part of the original Phases 0-13 — see
`docs/architecture_baseline.md` §12). Replaces the placeholder-level
`VoiceService`/`AudioService` (simulated sine wave, `simulate_command()`
identity pass-through, unchanged since Milestone 6/7) with real
speech-to-text, real text-to-speech, and real microphone capture — all
free/offline, all optional at runtime with graceful fallback to the
original simulated behavior if not installed.

## 1. What's built

| Piece | Library | Free? | Offline? |
|---|---|---|---|
| Mic capture | `sounddevice` (already a declared dependency, now actually used) | Yes | Yes |
| Speech-to-text | `vosk` | Yes | Yes — no API key, no usage limits |
| Text-to-speech | `pyttsx3` | Yes | Yes — uses whatever voices are already installed on the OS |

**The integration point already existed.** Phase 6/7 built
`AssistantCore.voice_command_received(text)` specifically so that "once
real STT exists, it only needs to call this method with the transcribed
text" (its own docstring, written before any of this existed). This work
is the first thing to actually use that seam — `process_voice_audio()` is
new, everything downstream of it (verification, conversation processing,
logging, events) is the same tested pipeline typed messages already use.

## 2. Confidence

Same honesty as the Flet migration: **none of this has been run.** This
sandbox has no audio hardware regardless of what's installed, and
`sounddevice` itself fails here at import time (`OSError: PortAudio
library not found` — confirmed by actually hitting it, not assumed),
which turned out to be a genuinely useful finding: the import-guard had
to catch `OSError` as well as `ImportError`, not just the latter, or this
exact real-world case (package installed, native library missing) would
have crashed instead of degrading gracefully.

What IS tested, without needing real hardware or the real packages
installed: the glue logic itself. `RealVoiceIO` in `test_all_phases.py`
(10 tests) uses a fake recognizer object to verify
`VoiceService.transcribe_chunk()`'s JSON-parsing and
finalized-vs-partial-utterance logic is correct, independent of whether
Vosk is actually present — plus the full graceful-degradation contract
(nothing raises when sounddevice/vosk/pyttsx3 are absent) and the
end-to-end routing through `process_voice_audio()` →
`voice_command_received()` → `process_message()`.

## 3. Setup — this is NOT just `pip install`

```bash
pip install vosk pyttsx3
```

That alone is not enough for STT. **Vosk needs a downloaded model
directory**, not bundled here — models run from ~40MB to several GB
depending on accuracy/language, and downloading one wasn't done blindly
on your behalf.

1. Download a model from https://alphacephei.com/vosk/models — the small
   English model (`vosk-model-small-en-us-0.15`, ~40MB) is the right
   starting point: fast, low-accuracy-but-usable, good for confirming the
   pipeline works before committing to a bigger model.
2. Unzip it so the result is a folder at
   `<repo root>/models/vosk-model-small-en-us-0.15/` (matches
   `VoiceService`'s `DEFAULT_MODEL_PATH`). A different location works too
   — pass `model_path=` explicitly when constructing `VoiceService` (in
   `assistant_core.py`) if you'd rather keep it elsewhere.
3. Without this folder present, `stt_available` stays `False` and
   `simulate_command()` keeps working exactly as before — nothing breaks,
   voice commands just aren't real yet.

`pyttsx3` needs nothing beyond the `pip install` — it uses whatever
voices are already on the OS (Windows: SAPI5 voices, already installed;
macOS: NSSpeechSynthesizer voices, already installed; Linux: needs
`espeak` installed separately, which most distros have as a
`pip install pyttsx3` transitive concern, not this project's).

## 4. What's wired into Nova's UI

The mic button now drives the full loop, not just audio capture:
`FletBridge.toggle_mic()` calls both `assistant.toggle_mic()` (audio
capture) and `assistant.start_voice_listening()`/`stop_voice_listening()`
(the separate listening-state flag `voice_command_received()` checks) —
these were two independent concepts since Phase 6/7 that nothing had
unified into one button press before this.

A new `_voice_loop` (same `page.run_task` pattern as the waveform loop)
polls `process_voice_audio()` every 300ms while both are active. Most
polls return `None` — that's the normal "still mid-utterance" case, not a
failure. When Vosk finalizes an utterance: the recognized text is pushed
to chat as a user bubble, the assistant's reply as an assistant bubble
(same as typed messages), and — new — `assistant.speak(reply.content)` is
called, so a voice command now gets a spoken reply, not just a text one.

**Not yet done**: the orb doesn't visually change state while TTS is
actually speaking (it reacts to `AssistantCore`'s conversation state —
idle/thinking/etc — but speech happens on a separate background thread
outside that state machine). A "speaking" visual cue is a reasonable
follow-up, not built in this pass.

## 5. How to test this for real

```bash
pip install vosk pyttsx3
# + download and place the Vosk model per §3
python flet_run.py --persona nova
```

Click the mic — it should now actually listen. Speak a short phrase.
Expect: after a brief pause (Vosk waits for silence to finalize an
utterance), your recognized text appears as a chat bubble, followed by
the assistant's typed reply, followed by hearing that reply spoken aloud.

Given nothing here has run yet, expect something to need a fix on the
first real attempt — report back whatever happens and we'll work through
it the same way the Flet UI bugs got resolved.
