# CLAUDE.md - waldoctl

`waldoctl` is the shared interface layer for Waldo Commander: the `Commander`
public-state API, the robot-client ABC, the panel/tool plugin ABCs, and the
dataclasses (`RobotStatus`, `Settings`, `Program`, `DryRun`, …) that the `parol6`
backend and the Waldo-Commander frontend both build on. Pure types and
contracts — it does no robot I/O.

## Testing Guidelines

- **No tautological tests.** Don't assert what's true by construction — e.g. a freshly built object's default field values. Test behavior, not the class's initializers.
