<!-- GENERATED FILE — do not edit. Regenerate with `pb registers`. -->

# Decision Stream

Flat, dated history of every committed design choice. Current state lives
in the layer leaves named by each record's `state:` field.

Records live in the cold-storage archive; extract one with `pb archive read <ID>`.

## By Layer

### Architecture

- **AD-001** — Keep the GUI repo separate and couple through the engine's plan schema · accepted · 2026-11-13 · `AD-001`
  The GUI stays a separate package and validates plan documents against the engine's normative flow-plan/2 JSON Schema.
