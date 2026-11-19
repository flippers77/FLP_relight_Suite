"""FLP Relight Pack - David Filipe / Electric Theatre Collective.
Copyright (c) 2026 David Filipe / Electric Theatre Collective. Internal use only - see LICENSE.

Packs the passes DF_comfy_relight needs into ONE ProRes 4444 movie per shot:

        +-----------+-----------+
        |  normal   |   depth   |      alpha channel = matte,
        +-----------+-----------+      repeated under every tile
        |  albedo   | irradiance|
        +-----------+-----------+

The movie is twice the width and height of the passes. In Nuke, read it with
colourspace = raw and plug it into the "pack" input of DF_comfy_relight, which
splits the tiles itself.

Nothing here converts colour: the numbers that come in are the numbers that are
stored (to the codec's 10-bit precision). Depth gets a tiny dither so that
precision limit shows as fine grain rather than visible steps.
"""
import os
import shutil
import subprocess

import numpy as np

LAYOUT = "FLP_RELIGHT_PACK v1 | 2x2 | top: normal, depth | bottom: albedo, irradiance | alpha: matte"


def _to_np(x):
    """IMAGE [N,H,W,C] or MASK [N,H,W] (torch or numpy) -> float32 numpy."""
    if x is None:
        return None
    if hasattr(x, "detach"):
        x = x.detach().float().cpu().numpy()
    return np.asarray(x, dtype=np.float32)


def _fit(a, h, w):
    """Resize a [N,H,W(,C)] array to h x w if it is a different size."""
    if a.shape[1] == h and a.shape[2] == w:
        return a
    try:
        import torch
        import torch.nn.functional as F
        t = torch.from_numpy(a)
        t = t.unsqueeze(-1) if t.dim() == 3 else t
        t = F.interpolate(t.permute(0, 3, 1, 2), size=(h, w), mode="bilinear", align_corners=False)
        t = t.permute(0, 2, 3, 1)
        return (t.squeeze(-1) if a.ndim == 3 else t).numpy()
    except ImportError:                       # nearest-neighbour fallback
        ys = (np.arange(h) * a.shape[1] / h).astype(int)
        xs = (np.arange(w) * a.shape[2] / w).astype(int)
        return a[:, ys][:, :, xs]


def _frame_of(a, i):
    """Frame i of a batch; a single-frame batch is held for the whole clip."""
    return a[min(i, a.shape[0] - 1)]


def _rgb(f):
    """One frame [H,W] or [H,W,C] -> [H,W,3]."""
    if f.ndim == 2:
        f = f[..., None]
    if f.shape[-1] == 1:
        f = np.repeat(f, 3, axis=-1)
    return f[..., :3]


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("FLP Relight Pack: ffmpeg was not found on this machine.")


def write_pack(path, normal, depth, albedo=None, irradiance=None, matte=None,
               frame_rate=25.0, quality="4444", dither_depth=True, ffmpeg=None):
    """Encode the atlas. Inputs are [N,H,W,C] / [N,H,W] arrays or tensors in 0..1.
    Returns (width, height, frames) of the movie written."""
    normal, depth = _to_np(normal), _to_np(depth)
    albedo, irradiance, matte = _to_np(albedo), _to_np(irradiance), _to_np(matte)
    n, h, w = normal.shape[0], normal.shape[1], normal.shape[2]
    h -= h % 2
    w -= w % 2
    normal = normal[:, :h, :w]
    depth = _fit(depth, h, w)
    albedo = None if albedo is None else _fit(albedo, h, w)
    irradiance = None if irradiance is None else _fit(irradiance, h, w)
    matte = None if matte is None else _fit(matte, h, w)
    frames = max(a.shape[0] for a in (normal, depth, albedo, irradiance, matte) if a is not None)

    cmd = [ffmpeg or find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba64le", "-s", "%dx%d" % (w * 2, h * 2),
           "-r", "%g" % frame_rate, "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=limited",
           "-sws_flags", "accurate_rnd+full_chroma_int+bitexact",
           "-c:v", "prores_ks", "-profile:v", "5" if quality == "4444 XQ" else "4",
           "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-metadata", "comment=" + LAYOUT, path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    rng = np.random.default_rng(0)
    black = np.zeros((h, w, 3), np.float32)
    try:
        for i in range(frames):
            d = _rgb(_frame_of(depth, i))[..., :1]
            if dither_depth:                  # +-1 code value of triangular noise, same on all channels
                d = d + (rng.random((h, w, 1), np.float32) - rng.random((h, w, 1), np.float32)) / 876.0
            top = np.concatenate([_rgb(_frame_of(normal, i)), np.repeat(d, 3, axis=-1)], axis=1)
            bottom = np.concatenate([black if albedo is None else _rgb(_frame_of(albedo, i)),
                                     black if irradiance is None else _rgb(_frame_of(irradiance, i))], axis=1)
            rgb = np.concatenate([top, bottom], axis=0)
            if matte is None:
                a = np.ones((h * 2, w * 2, 1), np.float32)
            else:
                m = _frame_of(matte, i)
                m = m[..., 0] if m.ndim == 3 else m
                a = np.tile(m, (2, 2))[..., None]
            frame = np.concatenate([rgb, a], axis=-1)
            proc.stdin.write((np.clip(frame, 0.0, 1.0) * 65535.0 + 0.5).astype("<u2").tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError("FLP Relight Pack: ffmpeg failed.\n" + err[-2000:])
    except BrokenPipeError:
        err = proc.stderr.read().decode("utf-8", "replace")
        raise RuntimeError("FLP Relight Pack: ffmpeg stopped early.\n" + err[-2000:])
    return w * 2, h * 2, frames


class FLP_RelightPack:
    """One packed ProRes 4444 with normal, depth, albedo, irradiance and a matte."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "normal": ("IMAGE", {"tooltip": "Normals, straight from the model. Do not colour-convert them."}),
                "depth": ("IMAGE", {"tooltip": "Depth as a grey image, near = white."}),
                "filename_prefix": ("STRING", {"default": "FLP/relight_pack",
                                               "tooltip": "Output path prefix, the same as a save node. '_RelightPack_<width>x<height>' is added."}),
                "frame_rate": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 240.0, "step": 0.001}),
                "quality": (["4444", "4444 XQ"], {"default": "4444",
                                                  "tooltip": "ProRes profile. XQ is larger; both are 10-bit here."}),
            },
            "optional": {
                "albedo": ("IMAGE", {"tooltip": "Optional. Leave unwired for a black tile."}),
                "irradiance": ("IMAGE", {"tooltip": "Optional. Leave unwired for a black tile."}),
                "matte": ("MASK", {"tooltip": "Optional. Goes in the alpha channel. Unwired = solid alpha."}),
                "dither_depth": ("BOOLEAN", {"default": True,
                                             "tooltip": "Adds very fine grain to the depth tile so 10-bit steps do not show in shadows."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filepath",)
    FUNCTION = "pack"
    OUTPUT_NODE = True
    CATEGORY = "FLP"
    DESCRIPTION = ("Pack relight passes into ONE ProRes 4444 movie for the DF_comfy_relight Nuke node: "
                   "normal and depth on the top row, albedo and irradiance on the bottom row, matte in the alpha.")

    def pack(self, normal, depth, filename_prefix, frame_rate, quality,
             albedo=None, irradiance=None, matte=None, dither_depth=True):
        import folder_paths
        # the size goes in the name, so a small review render never overwrites (or is mistaken for) the full-size one
        th, tw = int(normal.shape[1]), int(normal.shape[2])
        folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(
            "%s_RelightPack_%dx%d" % (filename_prefix, tw - tw % 2, th - th % 2), folder_paths.get_output_directory())
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "%s_%05d.mov" % (name, counter))
        w, h, frames = write_pack(path, normal, depth, albedo, irradiance, matte,
                                  frame_rate=frame_rate, quality=quality, dither_depth=dither_depth)
        print("[FLP] Relight pack: %s  (%dx%d, %d frames, %g fps)" % (path, w, h, frames, frame_rate))
        return {"ui": {"text": ["%s  |  %dx%d  |  %d frames  |  %g fps" % (path, w, h, frames, frame_rate)]},
                "result": (path,)}


NODE_CLASS_MAPPINGS = {"FLP_RelightPack": FLP_RelightPack}
NODE_DISPLAY_NAME_MAPPINGS = {"FLP_RelightPack": "FLP Relight Pack"}
