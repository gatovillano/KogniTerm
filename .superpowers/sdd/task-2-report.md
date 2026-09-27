# Task 2 Report: Scaffold `kogniterm-desktop` OpenCode Monorepo

## Summary
- **Status**: DONE
- **Commit**: `a69471df1d6040aea31e71f59bdb388e8ee2c430`
- **Branch**: `main`

## Implemented Actions
1. **Clean Prototype**:
   - Removed old Tauri/React prototype directories: `kogniterm-desktop/apps/` and old `kogniterm-desktop/packages/` (`types`, `ui`).
2. **Import OpenCode Packages**:
   - Copied OpenCode packages `desktop`, `app`, and `ui` from `/tmp/opencode_src/packages/` to `kogniterm-desktop/packages/`.
3. **Rebrand Scope & Packages**:
   - Replaced all `@opencode-ai/desktop` references with `@kogniterm/desktop`.
   - Replaced all `@opencode-ai/app` references with `@kogniterm/app`.
   - Replaced all `@opencode-ai/ui` references with `@kogniterm/ui`.
   - Rebranded package names in `package.json` (`@kogniterm/desktop`, `@kogniterm/app`, `@kogniterm/ui`).
   - Replaced "OpenCode" / "opencode" branding across user-facing texts, HTML window titles (`<title>KogniTerm</title>`), electron-builder configuration, electron windows, protocols (`kogniterm://`), store keys (`kogniterm.settings`), and i18n locales.
4. **Monorepo & Workspace Configuration**:
   - Created root `kogniterm-desktop/package.json` with workspace configuration (`workspaces: ["packages/*"]`) and npm scripts (`dev`, `dev:desktop`, `dev:app`, `build`, `typecheck`, `lint`).
   - Created root `kogniterm-desktop/turbo.json` with pipeline definitions matching Turborepo 2.x standard (`build`, `dev`, `typecheck`, and package-specific targets).
   - Resolved all Bun/Pnpm `catalog:` versions to concrete pinned semver versions from OpenCode's catalog.
   - Handled local vendoring of auxiliary packages (`@opencode-ai/core` and `@opencode-ai/session-ui` tarballs in `packages/app/vendor/`) to ensure full npm compatibility without `catalog:` or invalid `workspace:` protocol errors.
5. **Verification & Linking**:
   - Executed `npm install` inside `kogniterm-desktop/`: successfully linked workspaces (`@kogniterm/desktop`, `@kogniterm/app`, `@kogniterm/ui`) into `node_modules/@kogniterm/`.
   - Verified cross-workspace resolution: `@kogniterm/app` and `@kogniterm/ui` resolve directly across packages.
   - Tested Turbo pipeline: `npx turbo run typecheck --dry-run` accurately detects all 3 packages and their build targets.
   - Verified `@kogniterm/ui` builds cleanly with `npm --workspace=@kogniterm/ui run build`.

## Verification & Test Results
- `npm install` in `kogniterm-desktop`: Passed cleanly (`added 1249 packages, and audited 1253 packages`).
- Workspace links in `kogniterm-desktop/node_modules/@kogniterm/`:
  - `app -> ../../packages/app`
  - `desktop -> ../../packages/desktop`
  - `ui -> ../../packages/ui`
- `npx turbo run typecheck --dry-run`: Passed with all 3 packages in scope.
- `@kogniterm/ui` build (`rm -rf dist && tsc -p tsconfig.build.json`): Passed with 0 errors.

## Concerns / Notes
- None. Monorepo is ready for Task 3 (`KogniTermClient` API adapter & `sidecar.ts`).
