# Third-party models and tools used by the workflows

This repo contains no third-party model weights or code. The workflows load models you install separately. Licences below are as understood at time of writing; **verify each before client work**.

| Component | Used for | Licence (as understood) |
|---|---|---|
| UniVidX (+ Wan 2.1 T2V 14B base) | normals, albedo, irradiance | Apache-2.0 (verify the base model and adapters) |
| LightX2V step-distill LoRA | 4-step sampling | **Check** |
| DepthCrafter | depth | **Research / education only** (Tencent licence); built on Stable Video Diffusion (non-commercial). Not cleared for production. |
| SAM 2 (`sam2.1_hiera_base_plus`) | subject matte | Apache-2.0 |
| SAM 3 (test workflow only) | matte test | Meta SAM licence: royalty-free but with indemnity and redistribution terms. Needs legal review. |
| ffmpeg | writing the ProRes file | Depends on the build (LGPL / GPL). Not bundled. |

Video Depth Anything (small, Apache-2.0) was an earlier, production-safe alternative for depth.
