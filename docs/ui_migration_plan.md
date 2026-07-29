# ECLISPSIS‑AI — UI Migration Plan
Milestone 0 — Documentation Only

## 1. Current UI State
The repository contains no UI code.

## 2. Migration Goals
- All new desktop work uses PySide6 + QML.
- CustomTkinter is stabilization-only.
- PyQt6 prototypes may be ported only after inspection.
- Desktop remains in-process until API parity.

## 3. Target Desktop Structure
- Responsive navigation rail  
- Conversation + task workspace  
- Collapsible inspector  
- Diagnostics as secondary screen  
- Briefing region  
- Theme tokens, keyboard navigation, reduced motion  

## 4. Reactive Orb Contract
States: IDLE, LISTENING, THINKING, WORKING, SPEAKING, ERROR  
Reduced motion: static progress, color cues, labels.

## 5. Migration Sequencing
Milestones 1–5 define stabilization → core extraction → persistence → API → QML desktop.

## 6. Risks & Constraints
- Qt signal ownership  
- Worker thread safety  
- Accessibility requirements  
- No mixing CustomTkinter + Qt event loops  

## 7. Next Milestone
Proceed to Milestone 1 — Stabilize Current Behavior.

