# Jan integration

OpenMontage uses a patched build of Jan 0.8.0 as its local desktop chat shell.
Jan is Copyright 2025 Menlo Research and is distributed under the Apache
License 2.0; the upstream notice is retained in `LICENSE.upstream`.

The source tag, commit, archive digest, and output location are pinned in
`config/runtime/artifacts.json`. The custom executable is built on GitHub's
Windows runner so Visual Studio Build Tools never become a user prerequisite.
Validate or dispatch the build with:

```powershell
.\scripts\build_jan_portable.ps1 -ValidateOnly
.\scripts\build_jan_portable.ps1 -DispatchHostedBuild
```

The release contains the uninstalled Tauri executable, its SHA-256 sidecar,
build manifest, and upstream license. Setup downloads the pinned release asset
directly into `runtime/jan/`; it does not invoke a Jan installer or create
shortcuts. The maintained patch is applied with `git apply`; a source upgrade
must first pass `git apply --check` and all Jan/OpenMontage integration tests.

The initial patch adds a build marker. Task 9 of the implementation plan expands
the same patch with the permission selector, fixed provider/assistant view, MCP
context injection, and removal of online features.
