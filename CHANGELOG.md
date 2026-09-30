# Changelog

## 0.2.5 — 2026-09-30

### Added

- `pyfernet run -e/--entry REL`: override the encrypted package entry at runtime without re-encrypting. Path must be relative to the package root; absolute paths and `..` are rejected.
- Library: `run_payload(..., entry_point=...)` / `loader.main(..., entry_point=...)`.
- Demo second entry: `examples/demo_train/other_entry.py`.

### Notes

- Existing `.enc` payloads remain compatible. Upgrade the client to `pyfernet-payload>=0.2.5` to use entry override.
- Encrypt still records a default `entry_point` in the manifest; `run` without `-e` behaves as in 0.2.4.

## 0.2.4

Initial public release of `pyfernet-payload` (CLI `pyfernet` / `import pyfernet`).
