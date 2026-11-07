# CPU Animate — public runner integration notes

CPU Animate is an **independent, CPU-first** sports-video augmented-reality and alignment-validation system, developed privately in the CourtCoder ecosystem. The authoritative implementation plan and acceptance thresholds live in the private CourtCoder integration repository. This public runner may eventually execute tightly scoped **generic and rights-approved** CPU-only test jobs.

## Intended runner duties
- Pin Python, OpenCV, FFmpeg, raster backend versions and CPU architecture for reproducible tests.
- Run only pre-reviewed, content-safe unit tests, synthetic/rights-cleared visual fixtures and publicly releasable benchmark summaries.
- Measure decode, camera projection, optional mask, vector drawing, compositing and encode independently: CPU seconds, vCPU, peak RAM, wall time per video-second and actual hardware.
- Fail on camera cut continuity, unresolved time anchors, unsupported player identity, non-deterministic render/QA or unapproved source/rights.
- Produce machine-readable, provenance-preserving QA receipts without embedding protected source media.

## Security and provenance safeguards
- Original NBA XYZ, licensed video, credentials, signed HLS manifests, and private source assets remain outside this **public** runner repository and its artifacts.
- Public workflow templates must not fetch or cache NBA footage, scrape signed URLs, or transfer protected frames by default.
- The immutable production renderer and camera calibrations remain in their original private locations and must not be copied here.
- Graphics accuracy must be independently tested: camera landmark reprojection, foot alignment, original media PTS ↔ source UTC and player identity.
- A CPU drawing benchmark is NOT a measurement of full source-video throughput.
- Rights to use tracking data do not imply rights to publicly distribute modified NBA video.

## Status — 7 November 2026
This document is an execution integration note only. No GPU-free end-to-end CPU Animate render, three-angle aligned clip or production workflow is claimed by this file. Implementation must start with authorised deterministic fixtures and only graduate to actual footage after evidence and permission gates.
