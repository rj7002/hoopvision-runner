# HoopVision Runner

## rj7002 fork configuration

This is an attributed fork of [timeedmonds-maker/hoopvision-runner](https://github.com/timeedmonds-maker/hoopvision-runner). The upstream live Game Pulse workflow and collector are retained; this fork changes their private-destination settings so they can be configured for rj7002's own private data repository. Keep the upstream link and attribution when redistributing.

The live workflow is intentionally **not enabled in this fork yet**. Before enabling Actions, configure these repository settings:

- Repository secret `GAMEPULSE_PRIVATE_DATA_REPO`: your private repository slug (`owner/name`)
- Repository variable `GAMEPULSE_PRIVATE_DATA_BRANCH`: `gamepulse-original-captures`
- Repository secret `GAMEPULSE_PRIVATE_RELEASE_TOKEN`: a fine-grained token (or GitHub App token) scoped only to that private data repository, with Contents read/write and Releases access.

The token is never stored in this repository. Do not put it in workflow YAML, commit it, or print it in logs. The public runner repo contains workflow/source code only; captured source files must remain in the private destination. GitHub Actions is currently disabled for this fork while its workflows are being configured. This fork contains many unrelated upstream workflows, so enable only the reviewed live workflow; leave unrelated workflows disabled.

GitHub-hosted runners are temporary and scheduled runs can be delayed. The live workflow checks the official schedule every five minutes and uses per-game CPU jobs; it cannot guarantee an exact tip-off start. Review its final-whistle behavior and private storage before enabling it.

> **Integrated Pulse CPU execution boundary (28 Oct 2026):** source-native access is separate from strict acceptance. The private NBA tracking product now treats its conservative official NBA lineup/time acceptance subset as a research/quality cohort rather than a filter on the original captured source. Public CPU runners may verify private-source coverage and confidence strata **only** with the existing authorized ephemeral private checkout and source-integrity controls; original player/ball XYZ, proprietary actor traces, source data and detailed private candidate outputs must never be published here. Model promotions require private accepted QA. The private canonical PR documents the methodological decision; this public repository remains an orchestration layer only.


Public-safe execution bridge for CourtCoder/HoopVision.

This repository is **not** the product source and must never become a mirror of the private engine.

## Confidentiality boundary

Allowed here:
- generic bridge/orchestration code;
- generic privacy and security tests;
- synthetic, non-product fixtures;
- genuinely public-source utilities that reveal no private engine implementation, private evaluation state, cloud topology, credentials, source revision or retained evidence.

Forbidden here:
- private application source, model weights/checkpoints, private footage/fixtures/data/evidence;
- private source revisions/branches;
- algorithm-specific private-engine experiments and measured results;
- cloud project/bucket/service-account/build/operation/topology identifiers;
- credentials or authentication material;
- detailed private logs, failure traces or acceptance evidence.

**For the routine HoopVision/CourtCoder request bridge**, the only workload input crossing its public request/status boundary is a random opaque request ID. The separately scoped **Integrated Pulse Database** CPU Actions jobs below use a different, reviewed pattern: ephemeral workers authenticate to private `timeedmonds-maker/104`, process original NBA-source archives in ephemeral scratch space and write reports **only back to private `104`**. They are not sent through the routine opaque-request workflow, and their private payloads are never committed as public repository files or artifacts.

## Transport

The active canonical routine transport is:

`random opaque public request ID -> public outbox -> private pull consumer -> private registration/authorization -> private execution/evidence`

The public repository is only the request/status control surface. It does not receive private source, private evidence, private fixture identity, credentials, cloud authentication or direct GPU authority.

Routine CPU requests are consumed autonomously by private infrastructure. GPU work, when separately authorized, is also launched only from the private side; the public repository cannot authorize or directly dispatch GPU work.

A direct GitHub OIDC dispatch gateway remains a staged alternative only. It is **not** the active or canonical route until its private gateway and least-privilege path are separately verified and explicitly adopted.

## Public results

Public status is restricted to a minimal allowlist: request ID, coarse status, result-available boolean and observation time. Detailed metrics and failure evidence remain private.

See `PUBLIC_CONTENT_POLICY.md` and `runner_policy.json`.

## Approved Game Pulse CPU source-fusion jobs (2026–27)

This public repository also contains **orchestration-only** GitHub-hosted CPU workflows for an NBA Game Pulse data extension. The **private canonical repository** retains original source payloads, derived event-level records, and detailed acceptance results. Public repository commits, PRs, artifacts and logs **must never** contain player-level tracking, original SDK positions, query results, source secrets, video footage or copied private scripts.

Approved workflow roles:
- `.github/workflows/gamepulse-formal-pbp-14game.yml`: fetch source code transiently in the authenticated runner, validate official NBA play-by-play clocks and scores, write private results.
- `.github/workflows/gamepulse-native-interactions-14game.yml`: CPU fan-out of source-native tracking / official PBP / shot-event joins; result records are written **only** to the private repository.
- `.github/workflows/gamepulse-interaction-query.yml`: source-index-backed private player interaction query and private result write.
- `.github/workflows/rockets-native-touch-ppp.yml`: scoped original source/shot-alignment diagnostics, distinct from production indexed search.

**Scope note:** These purpose-built workflows are different from the opaque-request **CourtCoder execution transport** described above. They may fetch approved private code and data into an **ephemeral GitHub runner job**, subject to an authorized private access token and source SHA checks. The public *repository* never becomes a private mirror, and no private payload may be uploaded as a public artifact or printed to a public log. These actions do not grant a public user the ability to dispatch or approve private GPU execution.

**Source semantics and current workload contract:** official NBA play-by-play provides logical basketball possession identity, action ordering and outcomes; original Game Pulse source supplies dated physical observations linked privately through the accepted source time index. Native touch labels and geometric nearest-player estimates are not substitutes for the official event-defined possession identity or verified physical handover times. Public workflows perform ephemeral CPU validation and return private QA **only to the private canonical repository**. Source-specific implementation, private source revisions, metrics and numerical acceptance results stay exclusively in private documentation—not this public README.



## Integrated Pulse Database — separate NBA database workload

**Product name:** [Integrated Pulse Database](https://github.com/timeedmonds-maker/104/blob/main/INTEGRATED_PULSE_DATABASE.md) (private canonical repository). **Not** HoopVision image tracking, OCR, court calibration, prediction or Clip Lab. NBA Game Pulse refers to the original NBA tracking source; Integrated Pulse Database refers to the joined current-season tracking, NBA official PBP, Blueprint, lineup and query datasets.

This shared public GitHub repository provides **free GitHub-hosted CPU orchestration only** for independently scoped Integrated Pulse Database tasks. The private source release archives, NBA player/touch events, fused interaction indexes, scorer results and licensed XYZ stay in private `104` or ephemeral runner memory. Never expose per-player private results, tokens, source private revisions or raw positions in public logs, source files or public Actions artifacts.

| Reviewed workflow | Database operation |
|---|---|
| `.github/workflows/gamepulse-formal-pbp-14game.yml` | Check original 14-game official NBA clock and final score, publish private PBP receipt |
| `.github/workflows/gamepulse-native-interactions-14game.yml` | Fuse original native touch identities with PBP action runs and Blueprint in 14 parallel game jobs, save private per-game indexes |
| `.github/workflows/gamepulse-interaction-query.yml` | Run synthetic tests and saved three-player source-touch search over private indexed records |
| `.github/workflows/rockets-native-touch-ppp.yml` | Original Rockets source-native touch and independent event-clock control QA |

**Snapshot, 23 October 2026:** private original 14-game manifest has **8,701** NBA actions, **12,231** deduplicated native NBA Game Pulse touch records, **2,923** consecutive possession-team action runs and **14/14** final-score reconciliations. The saved Durant + VanVleet + Şengün query has **14 matching Rockets team action runs, 16 points and 1.142857 points/run**. Original Game Pulse touch records are treated as authoritative, without video/human touch recertification. The current counting unit is a team action run, not automatically an exact NBA offensive possession. See the private canonical documentation for provenance and the separate possession-accounting audit.

No statement above implies that these database jobs modify or validate the HoopVision/CourtCoder vision and prediction engines.
