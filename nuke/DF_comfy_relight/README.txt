DF_comfy_relight  v1.0
David Filipe / Electric Theatre Collective
==========================================
Relight a plate inside Nuke from a normals pass and a depth pass, such as the
ones ComfyUI produces. Eight draggable lights with cast shadows, a rim light
and a relit-albedo output. Every file here is original and yours to change.

FILES
  DF_comfy_relight.gizmo     the node
  DFComfyRelight.blink       the lighting kernel (plain text)
  DF_comfy_relight_ui.py     the light canvas and helpers
  menu.py                    toolbar entry: Nodes > ETC > DF_comfy_relight (Ctrl+Alt+R)
  df_banner.png              banner on the Setup tab
  df_logo.png, df_icon.png   logo and toolbar icon

INSTALL
  1. Copy this folder to   .nuke/DF_comfy_relight
  2. Add to .nuke/init.py: nuke.pluginAddPath('./DF_comfy_relight')
  3. Restart Nuke. Needs NukeX or Nuke Indie (BlinkScript) and Nuke 13+.

INPUTS  (in this order)
  0 pack       ONE packed movie from the FLP Relight Pack ComfyUI node. Read it
               with colourspace = raw. The node splits out normals, depth,
               albedo, irradiance and the matte (alpha) by itself.
  1 normals, 2 depth, 3 mask, 4 albedo, 5 irradiance
               Separate inputs. Each one overrides its tile of the pack when
               connected. Every input is optional.
  Nodes made with the earlier version have the inputs in a different order:
  create a fresh node rather than reusing an old one.

FRAME OFFSET
  ComfyUI movies start at frame 1. "passes start at frame" (Setup tab, default
  1001) shifts every input so frame 1 lands on 1001. Set it to 1 to switch off.

COLOUR (OCIO)
  Albedo and irradiance went into ComfyUI converted to out_rec709. The node
  converts them back to "ACES - ACEScg" with built-in OCIOColorSpace nodes
  (Setup tab, toggle "convert albedo / irradiance with OCIO"). Normals, depth and
  matte are data and are never converted. The names are checked against your
  OCIO config when the node is created; if one is missing the conversion is
  switched off and a warning appears in the Script Editor - pick the right
  names in the dropdowns. Read the pack as raw so Nuke does not convert twice.

  Passes from ComfyUI are smaller than the plate. Put a Reformat to plate
  size after this node (automatic reformat is planned).

OUTPUT
  Combined and the other views are lighting passes. "Relit (albedo x light)"
  multiplies your new lighting by the albedo for a finished relit image, with
  "keep original lighting" to mix the plate's own lighting back in.

FIRST RUN - THIS HAS NOT BEEN RUN IN NUKE YET
  Create the node, connect normals and depth, open the panel. Opening the panel
  compiles the kernel if needed and links every knob. If the picture is black
  or the node errors, press Setup > "reload kernel from file" and read the
  Script Editor. A compile error gives a line number in DFComfyRelight.blink.

GETTING COMFY PASSES TO SIT RIGHT
  * Depth Anything is near = white, so "depth: near is white" is ON by default.
    Untick it for passes where near is dark.
  * If light from the left lands on the right, tick flip X. If light from above
    lands underneath, tick flip Y. Different normal models disagree on these.
  * Set "subject depth" so the SUBJECT line sits where your actor is. Check with
    Output > Normals check, whose alpha is the depth the node is using.
  * Lights lower on the canvas than the SUBJECT line are in front of the actor.
  * Estimated depth is not real distance. Use "depth scale" to taste.
  * Shadows land on everything in the depth pass. Use the mask input to keep
    the relight on the actor.

EDITING
  Kernel: edit DFComfyRelight.blink, press "reload kernel from file".
  Look: colours and sizes are at the top of the Qt section in
  DF_comfy_relight_ui.py. Knob labels and defaults are in the .gizmo.
