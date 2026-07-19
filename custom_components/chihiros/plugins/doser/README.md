# Optional Doser plugin

This directory owns the Home Assistant Doser implementation:

- backend and dashboard assets
- entities and runtime interfaces
- protocol helpers and services
- storage and notification watcher

The LED Core does not import or register this plugin automatically. A future plugin loader may attach it through an
explicit, versioned Core interface without modifying the tested LED protocol, scheduler, services, or dashboard.

