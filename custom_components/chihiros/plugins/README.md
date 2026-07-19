# Chihiros Plugin Code

This package contains feature-specific code that is loaded by the main Home Assistant integration.

- `doser/`: dosing pump entities, services, storage, protocol helpers, and auto-total watcher.

The legacy top-level `doser_*.py` files are compatibility wrappers. New Doser code should be added under
`plugins/doser/` so the feature can continue moving toward separately updateable add-on packages without breaking
existing Home Assistant imports.
