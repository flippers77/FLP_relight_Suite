# DF_comfy_relight

Relight a plate in Nuke using passes generated in ComfyUI.

Original work by David Filipe / Electric Theatre Collective. Internal use only (see `LICENSE`).

```
 plate ──► ComfyUI workflow ──► one packed ProRes 4444 .mov ──► Nuke: DF_comfy_relight
           UniVidX  : normals, albedo, irradiance
           DepthCrafter : depth
           SAM2     : subject matte (click + track)
           FLP Relight Pack : packs all of the above into one file (matte in alpha)
```




## What is in this repo

| Folder | What it is |
|---|---|
| `nuke/DF_comfy_relight` | The Nuke gizmo: BlinkScript kernel, light panel (top-down canvas), menu entry. Needs NukeX or Nuke Indie (BlinkScript). |
| `comfyui/ComfyUI-FLP` | ComfyUI custom node **FLP Relight Pack**: writes the packed ProRes file. Needs ffmpeg. |
| `workflows/` | ComfyUI workflows (see below). Project, shot and asset names have been replaced with placeholders. |

## Install

**Nuke** (Windows and Linux): copy `nuke/DF_comfy_relight` to a folder on the plugin path (or add it with `nuke.pluginAddPath`), restart Nuke. The node appears under **Nodes > ETC > DF_comfy_relight** (default shortcut Ctrl+Alt+R). Details in `nuke/DF_comfy_relight/README.txt`.

**ComfyUI**: copy `comfyui/ComfyUI-FLP` into `ComfyUI/custom_nodes/` and restart ComfyUI fully. The node is **FLP Relight Pack** in the **FLP** category. Details in `comfyui/ComfyUI-FLP/README.txt`.

## Workflows

| File | Use |
|---|---|
| `relight_interim_no_FLP.json` | Works without the FLP node: one ProRes file per pass (albedo, irradiance, normals, depth; matte saver is muted until the SAM2 click is set). |
| `relight_packed_FLP.json` | Uses FLP Relight Pack: one packed file per shot. |

Settings (set in the workflow, notes inside explain each):
- **Working size:** 1280 (long edge) by default, in the resize node titled WORKING SIZE.
- **Frame cap:** 0 = whole shot (VoltLoader `frame_load_cap`). Use e.g. 49 for a quick look at a long shot.
- **`compile_dit`** (UniVidX loader): off for short shots, on for 200+ frame runs.
- **Frame rate:** one master value (25).
- Set the SAM2 click by running once with the savers muted so the editor shows the first frame. Only the **positive** wire is connected to the SAM2 node on purpose: an empty negative list makes the node fail.

Volt loader and filename-prefix nodes in the workflows are ETC pipeline nodes; set the placeholder project / shot values before running.

## In Nuke

1. Read the packed `.mov` (colourspace **raw**) and plug it into the `pack` input.
   Or plug separate passes into `normals`, `depth`, `albedo`, `irradiance`, `mask`.
2. Reformat the passes to the plate before the node.
3. Place lights on the **Lights** tab. Output modes: Combined, Lights, Shadows, Rim, Normals check, Relit (albedo x light).

## Status

Used in practice so far: the Nuke node and the interim (non-FLP) workflow in ComfyUI. Not yet confirmed end-to-end: the packed route through FLP into Nuke.

Known issues and planned work are tracked in `CHANGELOG.md`.

## Third-party models and licences

See `THIRD_PARTY.md`. Not everything the workflows load is cleared for client work. Read it before production use.
