# Changelog

## 0.2.0
- Nuke: `pack` is now the first input (order: pack, normals, depth, mask, albedo, irradiance). Recreate old nodes.
- Nuke: first-frame offset (default 1001) on every input.
- Nuke: built-in OCIO conversion for albedo / irradiance (out_rec709 -> ACES - ACEScg by default, names validated on node creation).

## 0.1.0 (initial repo)
- Nuke gizmo DF_comfy_relight: original BlinkScript kernel, top-down light canvas with head-and-shoulders subject, colour pick, subject depth, zoom. Optional inputs with fallbacks; `pack` input splits a packed file.
- ComfyUI node FLP Relight Pack (packed ProRes 4444, matte in alpha, size in filename).
- Workflows: interim (no FLP), packed (FLP), SAM3 matte test.
- HDRI controls removed from the UI (hidden knobs remain for the kernel).

## Planned / known
- Nuke: optional `plate` input and automatic reformat of the passes to it.
- Nuke: "plate + lights" output mode and highlight rolloff.
- Known: albedo can give hot values; passes can differ slightly in size from the plate (resize rounding / DepthCrafter size multiple of 64).
- ComfyUI: new ComfyUI release will need the nodes and workflows re-checked.
