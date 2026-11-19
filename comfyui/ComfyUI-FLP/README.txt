ComfyUI-FLP  v1.0
David Filipe / Electric Theatre Collective
==========================================
One node: FLP Relight Pack (category "FLP").

It packs the passes the DF_comfy_relight Nuke node needs into ONE ProRes 4444
movie per shot, twice the width and height of the passes:

    top row     normal      | depth
    bottom row  albedo      | irradiance
    alpha       matte (repeated under every tile)

INSTALL
  Copy the ComfyUI-FLP folder into ComfyUI/custom_nodes/ and restart ComfyUI.
  It needs ffmpeg on the machine (the same one the video save nodes use) and
  nothing else beyond what ComfyUI already has.
  If your ComfyUI is a managed studio release, this goes through whoever
  looks after that install.

INPUTS
  normal, depth            required
  albedo, irradiance       optional (black tile if unwired)
  matte                    optional MASK (solid alpha if unwired)
  filename_prefix          same as a save node; "_RelightPack_<width>x<height>" is added
  frame_rate               wire the workflow's MASTER FRAME RATE into it
  quality                  4444 or 4444 XQ
  dither_depth             fine grain on the depth tile, hides 10-bit steps

NOTES
  * Nothing is colour-converted. Read the movie in Nuke with colourspace = raw.
  * ffmpeg writes ProRes 4444 at 10 bits per channel. Tested round trip error
    is about half a 10-bit step per tile.
  * All inputs are resized to the normal pass's size if they differ.
