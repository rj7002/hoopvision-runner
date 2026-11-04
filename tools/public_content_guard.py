#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ALLOWED_STATIC = {
    ".github/workflows/curry-full107-ft-window-expansion-private-20261104.yml",  # reviewed: six-game SHA-original Curry source pre/post FT window audit, no private coordinates public
    ".github/workflows/curry-full107-original-ft-private-20261104.yml",  # reviewed: SHA-native six-game Curry FT audit; private-only source and per-shot result, public aggregates only
    ".github/workflows/r13-fc-original-contact-ladder-private-20261104.yml",  # reviewed isolated source SHA pinned four-game R13 audit; private-only original NBA XYZ/results
    ".github/workflows/r13-github-official-touch-paired-private-20261104.yml",  # private SHA-pinned five-game R13 original-source evaluation; zero private tracking public
    ".github/workflows/r13-official-snapshot-qa-private-20261104.yml",  # private, SHA-pinned public-NBA-count ingestion QA; only non-sensitive counts logged
    ".github/workflows/protected-private-source-stats.yml",  # generic pinned private CPU source task; no private payload or results public
    ".github/workflows/full92-private-unique-touch-ledger-v1.yml",  # reviewed: original SDK Full92 20-game private-only backfill and aggregate source-graded ledger QA
    ".github/workflows/gamepulse-55game-native-search-pr1030.yml",  # ephemeral SHA-verified private 55-game source-only search; public aggregate counts only
    ".github/workflows/gamepulse-sdk-only-partition-pr1030-tests.yml",  # SHA-pinned private synthetic-only SDK partition tests on free CPU; no licensed records public
    ".github/workflows/igp-full92-ball-tail-v10-private-20261103.yml",  # opaque protected native-ball tail source-masked evaluator (dedicated ref)
    ".github/workflows/igp-full92-controlled-ball-query-private-smoke-20261103.yml",  # private original observed-first Full92 ball query, no licensed XYZ public logs
    ".github/workflows/igp-full92-ball-control-1ft-capped-fresh18-private-20261103.yml",  # private fresh18 capped causal player-ball source-masked QA; aggregate public only
    ".github/workflows/igp-full92-controlled-ball-minimal-shrinkage-fresh12-20261103.yml",  # private frozen player/ball 25pct shadow on 12 NEW games, per-game SHA only
    ".github/workflows/igp-full92-ball-control-hybrid-unseen-private-20261103.yml",  # private dev-frozen owner-linear ball tracking shadows; aggregate public only
    ".github/workflows/igp-full92-causal-ball-control-forward-private-20261103.yml",  # private source-masked Full92 one-sided ball control v2; aggregate-only public QA
    ".github/workflows/igp-full92-controlled-ball-persistence-private-20261103.yml",  # private original NBA Full92 player-relative ball source-mask and natural gap candidate QA; aggregate public only
    ".github/workflows/igp-full92-ball-flight-physics-shadow-private-20261103.yml",  # private NBA XYZ source-masked gravity flight test; aggregate no coordinates public
    ".github/workflows/gamepulse-full92-event-query-verified-readback-20261103.yml",  # public-safe Full92 private source event query/pointer SHA readback; aggregate tests only
    ".github/workflows/gamepulse-full92-universal-event-rebound-tracking-20261103.yml",  # private full92 original NBA event, rebound and XYZ provenance; aggregate-only public logs
    ".github/workflows/igp-full92-new4-masked-holdout-private-20261102.yml",  # SHA-pinned unseen game source masking; no private rows public
    ".github/workflows/igp-full92-native-census-private-20261102.yml",  # SHA-pinned private 92-game intake census; aggregate pass only public
    ".github/workflows/igp-full88-guard-discrepancy-pilot-20261102.yml",  # pinned private one-game source forensic; aggregate-only public output
    ".github/workflows/igp-full88-v4-single-p2b-promote-private-20261102.yml",  # private-source full88 5904 single-player v4 release/rollback gate; public PASSFAIL only
    ".github/workflows/igp-full88-single-source-qualified-private-20261102.yml",  # private source-pinned limited 6237 natural-gap single-actor acceptance QA; aggregates only
    ".github/workflows/igp-full88-natural-gap-enriched-private-20261102.yml",  # private SHA original NBA sparse-anchor masked source holdout, no individual stats public
    ".github/workflows/igp-full88-natural-gap-new17-masked-private-20261102.yml",  # source-masked 17-game original NBA actor/ball private accuracy QA; aggregate-only public
    ".github/workflows/igp-full88-natural-gap-qualified-private-20261102.yml",  # private Full88 exact marginal original anchor-gap classification; no NBA data in public logs
    ".github/workflows/igp-full88-parallel-exact-marginal-private-20261102.yml",  # exact four-way Full88 private NBA original source scene overlap, aggregate CI only
    ".github/workflows/igp-full88-exact-unguarded-marginal88-private-20261102.yml",  # SHA-pinned private NBA Full88 exact 10Hz guarded-versus-unguarded scene overlap; safe counts only
    ".github/workflows/igp-full88-new17-p2b-shortgap-private-20261102.yml",  # private 17-game masked-original new-cohort P2B guard evaluation; aggregates only public
    ".github/workflows/igp-full88-unguarded-p2b-marginal-private-20261102.yml",  # PINNED private 88-game research option and 63-unseen masked-source QA; no licensed rows in public
    ".github/workflows/igp-full88-v3-guarded88-private-gate-20261102.yml",  # audited: licensed SHA-native 7-game 10Hz P2B source acceptance; private-only real scenes, aggregate log
    ".github/workflows/igp-full88-all88-original-pbp-chain-private-20261102.yml",  # private exact-NBA-PBP source original-chain accounting all 88
    ".github/workflows/igp-full88-boxscore-176-private-20261102.yml",  # opaque 88 game, 176 team original NBA PBP/boxscore, team OREB/FTA audit
    ".github/workflows/igp-full88-new7-guarded-10hz-private-20261102.yml",  # protected original NBA full88 last7 official-ten P2B 10hz masked source shadow, aggregate public
    ".github/workflows/igp-full81-boxscore-all-source-private-20261102.yml",  # private 81-game NBA original PBP/official boxscore FT+OREB provenance, no original rows public
    ".github/workflows/igp-full81-nba-poss-definition-private-20261102.yml",  # private-only NBA PBP vs published team POSS formula sensitivity, no provider claims/logs
    ".github/workflows/igp-full81-original-pbp-terminal-atlas-private-20261102.yml",  # opaque source-private original NBA PBP full81 terminal/poss discrepancy replay
    ".github/workflows/igp-full88-0004-original-feature-revision-private-20261102.yml",  # private-only Blueprint source shot-field diff after changed provider SHA, only aggregate public results
    ".github/workflows/igp-full88-three-gap-blueprint-fresh-private-20261102.yml",  # private-only first-party NBA Blueprint revision recheck on three missingness games, aggregate public outputs
    ".github/workflows/igp-full88-shot-source-rootcause-private-20261102.yml",  # opaque private 88-game original Blueprint vs exact shot-identity rootcause; aggregates only public
    ".github/workflows/igp-full88-v2-official-176-team-poss-acceptance-20261102.yml",  # protected private SHA-pinned FULL88 statistical v2 test, aggregate logs only
    ".github/workflows/igp-full88-176-published-team-poss-private-gate-20261102.yml",  # opaque official NBA 176 team-game published POSS and PBP score verification
    ".github/workflows/igp-full88-176team-official-poss-private-20261102.yml",  # SHA-locked private NBA source-only 176 team-game published-POSS gate; public aggregates only
    ".github/workflows/igp-full88-two-game-blueprint-source-recheck-20261102.yml",  # reviewed original Blueprint two-game private SHA recheck; aggregate-only public logs
    ".github/workflows/igp-full88-foundation-recoverability-20261102.yml",  # vetted opaque SHA-private Full88 shot recoverability and 81game POSS QA; public aggregates only
    ".github/workflows/courtcoder-p1-protected-control-tests.yml",  # protected ephemeral private-code unit tests; no private model/video/labels in public repo or logs
    ".github/workflows/ncea-full88-rebound-tier-private.yml",  # reviewed SHA-original private-only rebound event-tier source audit and bounded aggregate logs
    ".github/workflows/ncea-full88-rebound-physical-private.yml",  # reviewed opaque pinned NBA-source Full88 rebound candidate and masked QA; detailed data private only
    ".github/workflows/ncea-full88-multi-event-original-shadow-private.yml",  # reviewed opaque source-pinned private-only Full88 event QA; public aggregate counts only
    ".github/workflows/ncea-full88-original-custody-private.yml",  # private 4616-event NCEA original SDK shadow and controls; public aggregate counters only
    ".github/workflows/assist-pair-chart-private-smoke.yml",  # reviewed: source-locked private Full88 assist pair exact QA, no private event data in public logs
    ".github/workflows/full88-private-lateclock-interior-v2.yml",  # opaque Full88 inter-event Time#show PBP clock joined privately; aggregate-only public status
    ".github/workflows/igp-full88-all-official-assists-private.yml",  # reviewed: original NBA PBP/box and derived assist ledger written to private 104 only; public aggregate counts
    ".github/workflows/gamepulse-full88-sengun-assist-court-20261102.yml",  # private Full88 official PBP and SHA original SDK assist-location audit; aggregate public log only
    ".github/workflows/igp-full88-ten-shot-motion-private-20261101.yml",  # 10 NBA original XYZ and provisional 10Hz privately only; public aggregates only
    ".github/workflows/igp-full88-clips-all-links-private-repair-20261101.yml",  # opaque private-only 88-game SHA-preserving event URL repair; public aggregate counts only
    ".github/workflows/nba-clip-deeplink-10shot-public-probe-20261101.yml",  # public NBA URL status probe only; no private data
    ".github/workflows/igp-full88-jabari-durant-shotmatch-20261101.yml",  # private-only SHA-verified five-pair matching; aggregate public log only
    ".github/workflows/igp-full88-default-promotion-private-20261101.yml",  # reviewed bounded FULL88 private-source SHA default smoke, aggregate-only public output
    ".github/workflows/igp-full88-multiangle-shots-private-20261101.yml",  # private-only 88game source SHA event, biomechanics, original native and NBA clip-ID join; public counts only
    ".github/workflows/gamepulse-full88-0153-verified-original-backfill.yml",  # reviewed official-final NBA 0153 bounded SDK 13part capture, SHA private release + companion source and FULL88 index
    ".github/workflows/gamepulse-full88-ready13-certify-20261101.yml",  # source-private existing 13-part SDK readback for verified 31 Oct games; no original XYZ public
    ".github/workflows/gamepulse-full107-ready13-recovery-20261103.yml",  # reviewed: original 13-part SHA-only Full107 repair; licensed coordinates confined to private 104
    ".github/workflows/gamepulse-full107-missing35-source-20261103.yml",  # reviewed: exact 35 missing authentic SDK parts; SHA archives/private indexes only
    ".github/workflows/igp81-opponent3-prior-shooters-v2.yml",  # SHA-locked public 2025-26 prior plus private original NBA FULL81; aggregate public
    "tools/licensed_feed/igp81_opponent3_prior_shooters_v2.py",  # historical shooter priors, no licensed source rows in public output
    ".github/workflows/igp81-opponent3-luck-source-audit-v1.yml",  # private full81 SHA PBP and Blueprint exploratory output, public aggregate only
    "tools/licensed_feed/igp81_opponent3_luck_source_audit_v1.py",  # deterministic Python reads original privately, emits only aggregate source checks
    ".github/workflows/nba-eason-0022600153-replay-access-probe.yml",  # reviewed public official NBA replay URL response-only tester; no private data
    ".github/workflows/igp81-n2pp-offline-v10.yml",  # reviewed opaque 81game NBA-original and Blueprint-only fallback, output aggregate privately
    ".github/workflows/igp81-n2pp-official-first-audit-v3.yml",  # reviewed opaque N2PP private 81-game official-first census; no licensed data in public
    ".github/workflows/igp81-three-two-possession-private.yml",  # reviewed private 81-game shot-next-possession aggregate-only executor
    ".github/workflows/private-analysis-cpu-shard.yml",  # generic protected ephemeral private-source analytics; only private QA output
    ".github/workflows/private-analysis-reduce-only.yml",  # pinned R10 retry; SHA-verifies >1MiB Git blobs; no source/model bytes or private results in public logs
    "tools/licensed_feed/igp81_test_default_shot_route.py",  # deterministic source-free private default 81game shot acceptance
    "tools/licensed_feed/igp81_wire_default_shots.py",  # deterministic source-free private default 81game shot acceptance
    ".github/workflows/igp81-default-shot-detail-integration.yml",  # private-only QA-validated 81game default shot route
    "tools/licensed_feed/igp81_default_shot_detail_query.py",  # source-free original 81game shot read-only interface
    ".github/workflows/igp81-source-adjusted-10hz.yml",  # private original SDK availability source mask; public only aggregate metrics
    "tools/licensed_feed/igp81_source_availability_800ms_audit.py",  # source-free 81game availability QA transform executed privately
    ".github/workflows/igp81-position-source-native-delta.yml",  # original SDK private XYZ timestamp/actor SHA delta; public aggregate only
    ".github/workflows/igp81-detailed-source-release-lock.yml",  # source SHA all81 verified private-only query and QA; safe public aggregates
    ".github/workflows/igp81-companion-positions-variant-probe.yml",  # first-party authorized SDK variant, original JSON saved private only
    ".github/workflows/igp81-promote-source-grade-detail.yml",  # private-only 81-game SHA-graded shot detail acceptance, aggregate public release status
    ".github/workflows/igp81-three-gap-companion-recovery.yml",  # licensed SDK authorized three-game source retry, raw privately preserved only
    ".github/workflows/igp81-retry-missing-three-companion.yml",  # authorized SDK retries of three unavailable original event programs; private-only source
    ".github/workflows/igp81-detailed-layers.yml",  # private SHA-verified 81-game Blueprint/biomechanics release; aggregates only public
    "tools/licensed_feed/igp81_complete_detail_layers.py",  # source-only Python transform; licensed data never committed to public
    ".github/workflows/gamepulse-igp81-oct30-companion-final-join.yml",  # private immutable NBA original companion SHA readback, public aggregate status only
    ".github/workflows/gamepulse-igp81-sdk-original-recovery-20261101.yml",  # private NBA SDK source recovery, private-only source and sanitized public status
    ".github/workflows/gamepulse-igp-p2b-team-offrtg-81-same-grain-20261101.yml",  # pinned private PBP score/possession audit; aggregate-only public QA
    ".github/workflows/gamepulse-igp-p2b-nba-style-oreb71-v1.yml",  # private 71 NBA PBP OREB continuation phase analysis; aggregate-only public QA
    ".github/workflows/gamepulse-igp-p2b-player-poss-credit-policy-all71.yml",  # private SHA original 71 PBP and public NBA rotation overlap policy: aggregate only

    ".github/workflows/gamepulse-igp-p2b-possession-alignment-g1-all71-20261031.yml",  # SHA-original 71 PBP candidate sequence QA + 81 NBA team advanced public mirror; aggregate-only public logs

    ".github/workflows/igp-71-nba-team-player-k2-k5-hierarchy-source-audit.yml",  # private source IGP 71 immutable PBP plus NBA advanced player and rotation k-level graded audit
    ".github/workflows/igp-2027-player-team-lineup-possession-consistency-probe.yml",  # public NBA Stats team/player mirror + official NBA lineup k=2/3/4/5 bounded probe
    ".github/workflows/gamepulse-igp-71-player-poss-stint-triage-20261031.yml",  # read already accepted private QA and emit aggregate sanitized possession substitution variance targets
    ".github/workflows/gamepulse-igp-71-player-offrtg-rotation-possession-audit-20261031.yml",  # reviewed original 71game NBA player OffRtg, POSS and substitution rotation source private QA
    ".github/workflows/gamepulse-igp-2027-player-advanced-rotations-probe-20261031.yml",  # public NBA advanced player-game and rotation parquet source schema only
    ".github/workflows/gamepulse-igp-open-nba-advanced-71game-crosswalk-20261031.yml",  # mirror NBA 2027 advanced team stats source-verified 71game private PBP comparison, aggregate only
    ".github/workflows/gamepulse-igp-open-nba-advanced-parquet-probe-20261031.yml",  # public NBA stats mirror DuckDB metadata and two source game ratings only
    ".github/workflows/gamepulse-igp-71-offrtg-inverse-original-source-audit.yml",  # reviewed private NBA 71game score and 17 advanced displayed-rate inversion; public aggregate only
    ".github/workflows/gamepulse-igp-71-offrating-official-probe.yml",  # approved official NBA advanced game-level rate, printed aggregate only
    ".github/workflows/gamepulse-igp-p2b-partial-native-action-evidence-all71-20261031.yml",  # source-private 71game partial actor+ball NBA action evidence; public aggregates only
    ".github/workflows/gamepulse-igp-p2b-native-p2b-action-union-all71-20261031.yml",  # private all71 SHA original native plus P2B bounded action evidence dedup union; aggregate logs only
    ".github/workflows/gamepulse-igp-p2b-native-action-source-evidence-20261031.yml",  # private original NBA 71game 500ms native ten+ball scorer action source QA; public counts only
    ".github/workflows/gamepulse-igp-p2b-original-native-action-context-all71-20261031.yml",  # SHA private all71 NBA original native action context; only aggregate public logs
    ".github/workflows/gamepulse-igp-p3-p2b-0146-source-shadow.yml",  # private original NBA SHA P3 vs P2B 0146 masked source QA; only aggregate outputs public
    ".github/workflows/gamepulse-igp-v32-event-alignment-fixed-p2b-regression.yml",  # reviewed private original 71game exact P2B source mask regression no licensed raw positions in logs
    ".github/workflows/gamepulse-igp-v32-universal-event-query-smoke.yml",  # reviewed source SHA original PBP lineup and default P2B 10Hz single-event join, aggregate-only public logs
    ".github/workflows/gamepulse-igp-multiagent-p2b-disjoint-masked-qa.yml",  # private SHA-backed 71-cohort P2B vs P3 4-game disjoint original-source mask, aggregate metrics only
    ".github/workflows/gamepulse-igp-p2b-original-nearest-source-reconcile-20261031.yml",  # reviewed SHA private PBP action closest-original UTC ambiguity audit, public counts only
    ".github/workflows/gamepulse-igp-p2b-event-query-smoke-20261031.yml",  # private licensed original source 12-event P2B query readback; public aggregate only
    ".github/workflows/gamepulse-igp-v32-71-clock-disagreement-triage.yml",  # private SHA source PBP SDK companion clock conflict triage, public counts only
    ".github/workflows/gamepulse-igp-p2b-action-context-20261031.yml",  # reviewed private NBA all71 action-window context; only aggregate totals public, original XYZ private
    ".github/workflows/gamepulse-igp-p2b-all-action-tracking-20261031.yml",  # reviewed private-SHA 71game P2B original official action crosswalk; public aggregate QA only
    ".github/workflows/gamepulse-igp-v32-event-roster-substitution.yml",  # official NBA original SHA PBP 71-game pre/post substitution roster context, no licensed XYZ public logs
    ".github/workflows/gamepulse-igp-v32-universal-event-possession-alignment.yml",  # private SHA original 71game PBP event / logical possession / native SDK full census, aggregate-only public logs
    ".github/workflows/gamepulse-igp-v32-nineball-short-source-anchor.yml",  # private original SDK nine+ball same-official-ID short source anchor masked evaluation
    ".github/workflows/gamepulse-igp-v32-0146-app-clock-readback.yml",  # private SHA original 0146 user app 3 stop align & guarded P2B; public aggregate counts only
    ".github/workflows/gamepulse-igp-v32-extra-actor-fifth-crosswalk.yml",  # private original SDK 71g fifth-player extra-actor crosswalk and synthetic ID holdout aggregates
    ".github/workflows/gamepulse-igp-v32-71-incomplete-scene-census.yml",  # reviewed IGP all71 missing-player and ball aggregate-only census
    ".github/workflows/gamepulse-igp-v32-p2b-guarded-default-preflight.yml",  # private-SHA P2B guarded candidate 10Hz default rollback/source QA, public aggregate-only
    ".github/workflows/gamepulse-igp-v32-p2b-guarded-source-readback.yml",  # guarded P2B private source three-game QA, aggregate-only redacted public logs
    ".github/workflows/gamepulse-igp-v32-p2b-63unseen-locked1200-gate.yml",  # private original 63 unseen SHA-source 1.2s release gate, no physical promotion
    ".github/workflows/gamepulse-igp-v32-p2a-71game-source-extreme-tail.yml",  # exact 71 source heldout source motion tail forensic, no original XYZ in public
    ".github/workflows/gamepulse-igp-v32-p2b-63unseen-71game-source.yml",  # private SHA original 1.2s 63 unseen NBA dev holdout and 71game coverage
    ".github/workflows/gamepulse-igp-v32-p2b-eightgame-bidirectional-source.yml",  # source SHA private two-side 1.2/1.8s 3plus actor 1-2s hard blackout pilot
    ".github/workflows/gamepulse-igp-v32-p2a-locked-71source-gate.yml",  # private SHA 71game P2A heldout DEV VAL gate, research only no physical claim
    ".github/workflows/gamepulse-igp-v32-p2a-scene-query-real.yml",  # read-only private original NBA P2A two-player ball bounded source scene query regression
    ".github/workflows/gamepulse-igp-v32-p2a-71game-joint-hardblackout.yml",  # strict S1 source-native all71 reconstruction challenger and masked player XY QA, private-only
    ".github/workflows/gamepulse-igp-v32-v10-all71-native-pbp-query.yml",  # 54 companion plus 17 PBP-only original native all71 NBA unified query acceptance
    ".github/workflows/gamepulse-igp-v32-v9-17game-no-companion-native.yml",  # SHA-original remaining 17 NBA game native to PBP-only index; private provenance
    ".github/workflows/gamepulse-igp-v32-v8-unified-native-chain-query.yml",  # original SDK native + strict S1 bounded read-only two-population official NBA chain query QA
    ".github/workflows/gamepulse-igp-v32-v7-native-official-chain-54.yml",  # private 54game original-native 71 NBA logical PBP time crosswalk, public aggregate only
    ".github/workflows/gamepulse-igp-v32-v7-unified-fast-pbp-native-query.yml",  # 71game fast PBP metadata preserves defaults; opt-in 54game source-native SHA XYZ, no licensed logs
    ".github/workflows/gamepulse-igp-v32-v5b-native-to-official-pbp-54.yml",  # 54game private SHA-native-to-unique-logical-NBA-PBP UTC bridges no licensed coordinates in public runner
    ".github/workflows/gamepulse-igp-v32-v6-original-release-39parts.yml",  # 3game 39 original SDK private release part SHA-vs-index forensics; public aggregate only
    ".github/workflows/gamepulse-igp-v32-v5-original-native-postings-54.yml",  # private SHA-native 54-game outside-S1 exact source observations index; no licensed XYZ in public logs
    ".github/workflows/gamepulse-igp-v32-v2d-sixgame-original-clock-voids.yml",  # 6game SHA-private original SDK source time-void QA no licensed XYZ or UTC in public logs
    ".github/workflows/gamepulse-igp-v32-v3b-outside-s1-original-native.yml",  # SHA-private original SDK native XYZ census for clock-corrob time outside strict S1; public aggregate counts only
    ".github/workflows/gamepulse-igp-v32-v3-companion-clock-54.yml",  # reviewed SHA-private 54game Time-event clock corroboration; no source XYZ or broadcast video in public logs
    ".github/workflows/gamepulse-igp-v32-v4-fast-possession-index.yml",  # reviewed SHA-private 71game logical-PBP metadata materialization; public only counts and 3 latencies
    ".github/workflows/gamepulse-igp-v32-possession-ID-default-query-smoke.yml",  # reviewed: private 71game NBA PBP chain 10Hz original native source; public only IDs, counts and measured latency
    ".github/workflows/gamepulse-igp-v32-71game-possession-10hz-source-qa.yml",  # reviewed: original NBA SHA-private 71game 10Hz logical-chain QA, only pergame counts public no player XYZ
    ".github/workflows/gamepulse-igp-v32-default-10hz-release-regression.yml",  # reviewed: permanent 71game private SHA original source 10Hz source-QA engine lock, only IDs/grades/totals public
    ".github/workflows/gamepulse-rockets-0022600021-q2-tail-source.yml",  # NBA licensed SDK 0021 elapsed Q2 tail direct source SHA private release only
    ".github/workflows/gamepulse-rockets-0022600021-official-10hz.yml",  # exact NBA first-party PBP+five starters official S1 accepted engine private XYZ and aggregates only
    ".github/workflows/gamepulse-rockets-0022600021-official-source-recovery.yml",  # official NBA PBP box+licensed companion source-only acquisition; private artifacts, public safe status only
    ".github/workflows/gamepulse-rockets-0022600021-firsthalf-model-b.yml",  # SHA-private original player source Model B gapfill, masked QA, aggregate public logs only
    ".github/workflows/gamepulse-rockets-0022600021-firsthalf-backfill.yml",  # reviewed first-half NBA SDK SHA original private-only release backfill; public aggregate source QA only
    ".github/workflows/gamepulse-igp-v32-per-actor-0006-pilot.yml",  # reviewed: SHA-original 13part 0006 selected actor/ball provenance; private metadata and XYZ; aggregate-only public logs
    ".github/workflows/gamepulse-igp-v32-source-grade-query-v2.yml",  # private original NBA per-ball SDK upstream source grade query smoke; no licensed XYZ output
    ".github/workflows/gamepulse-igp-v32-existing-ball66-forensic.yml",  # reviewed SHA-private source original 0006 66ft masked ball baseline discrepancy forensic
    ".github/workflows/gamepulse-igp-v32-ball-source-quality-query-smoke.yml",  # source private optin query warning tests no original player xyz public
    ".github/workflows/gamepulse-igp-v32-ball-source-variant-0001.yml",  # verified original SDK thirteen-part private ball raw variant audit no public XYZ
    ".github/workflows/gamepulse-igp-v32-consecutive-live-bridge-all71.yml",  # source-private original NBA 71 same-lineup live PBP source bridge research, aggregate-only logs
    ".github/workflows/gamepulse-igp-v32-consecutive-live-segment-bridge-pilot.yml",  # reviewed SHA-private same-official-roster adjacent clock-running NBA PBP bridge source masked research
    ".github/workflows/gamepulse-igp-v32-ball-40ft-source-forensics.yml",  # private NBA source original ball discrepancy and spike confirmation; safe aggregate only
    ".github/workflows/gamepulse-igp-v32-ballonly-hazard-all71.yml",  # private SHA-original ball hazard scene census and masked error QA all71, public safe totals only
    ".github/workflows/gamepulse-igp-v32-ballonly-hazard-sixgame.yml",  # SHA-private NBA original 71 selected 6game masked ball 3D hazard context research QA only
    ".github/workflows/gamepulse-igp-v32-ball-0001-tail-dossier.yml",  # reviewed private NBA game0001 source masked 40ft error falsification, aggregate only
    ".github/workflows/gamepulse-igp-v32-ballonly-unseen65-source-mask.yml",  # reviewed SHA-private IGP v32 65-game disjoint masked ball model source QA, aggregates only
    ".github/workflows/gamepulse-igp-v32-ballonly-sixgame-pilot.yml",  # reviewed source-private sixgame shadow ball-only speed QA; public aggregate only
    ".github/workflows/gamepulse-igp-v32-71-dualgrid-recovery-census.yml",  # reviewed private SHA 71game 10+ball root-cause census, public aggregates only
    ".github/workflows/gamepulse-igp-71-booker-approved-id-live-gain.yml",  # pre-approved 0092 Booker official ID only, private original SHA live 800/1200 aggregate, no public XYZ
    ".github/workflows/gamepulse-igp-71-halfcourt-research-smoke.yml",  # source original NBA append3 all6 halfcourt source-grade outputs, public aggregate counters only
    ".github/workflows/gamepulse-igp-71-full-valid-gains-holdout.yml",  # reviewed private original NBA all71 masked source player XY and ball 3D 800/1200; public aggregate only
    ".github/workflows/gamepulse-igp-71-valid-gains-gates.yml",  # reviewed 71 original NBA source SHA and matched masked 800/1200 quality gates; aggregate public counts only
    ".github/workflows/gamepulse-igp-71-new3-live-play-source-qa.yml",  # private SHA original NBA three added games same live clock 800/1200 metrics; public only safe aggregate counts
    ".github/workflows/gamepulse-igp-v31-71-integration-qa.yml",  # private 71-game SHA metadata only, source-graded metric tests, no XYZ or media in public logs
    ".github/workflows/gamepulse-igp-crash-the-glass-20261031.yml",  # frozen 68-game crash-the-glass private-only research, aggregate public counters
    ".github/workflows/gamepulse-igp-g3-shot-targeted-68-2400ms-source-qa.yml",  # private NBA68 SHA-original shot targeted all-actor blackout disjoint 34/34 validation aggregate only
    ".github/workflows/gamepulse-igp-g3-nba-shot-conditional-ball-68-holdout.yml",  # SHA NBA original source shot-semantic 34dev34val 2400ms source-masked ball3D tail QA only
    ".github/workflows/nba-public-orebpct-research-20261031.yml",  # reviewed independent public NBA official rebounding stats research only, no private XYZ
    ".github/workflows/gamepulse-igp-g3-motion-disjoint-68-2400ms.yml",  # private original NBA G3 motion dev34 vs heldout34 source masked 2p4s, only aggregate logs
    ".github/workflows/gamepulse-igp-g3-68-fullscene-2400ms-source-holdout.yml",  # 68game all-actor source original NBA 2400ms G3 blackout accuracy, aggregate only
    ".github/workflows/gamepulse-igp-g3-all68-conflict-physical-source-holdout.yml",  # private exact original NBA full68 G3 actor conflict recon source-only masked player/ball accuracy aggregate
    ".github/workflows/gamepulse-igp-g2-post36-all32-increment.yml",  # private original NBA 32 box and PBP roster replay, aggregate safe counts only
    ".github/workflows/gamepulse-igp-fifth-extra-actor-diagnostic.yml",  # private source all68 actor alias audit, public aggregate counts only
    ".github/workflows/gamepulse-igp-g2-legacy36-plus-68-bridge-acceptance.yml",  # original NBA 36 G2 SHA-verified long+sub source evidence aggregated with 68 short bridges private QA
    ".github/workflows/gamepulse-igp-fusion-fifth-player-all68.yml",  # SHA-pinned private NBA roster-only fifth identity census; aggregate public counts
    ".github/workflows/gamepulse-igp-71-final-blueprint-aggregate-readback.yml",  # reviewed 71game original source Blueprint private QA; public log aggregate only
    ".github/workflows/gamepulse-igp-g2-all68-official-sameten-bridge.yml",  # 68 NBA source SHA two-ended official lineup candidate bridge audit, aggregate public only
    ".github/workflows/gamepulse-igp-fusion-sourcefirst-all68-qa.yml",  # source-first 68 game immutable NBA XYZ actor/ball visibility census, safe aggregates only
    ".github/workflows/gamepulse-igp-p4-human-app-sourcefirst-native-heldout-v2.yml",  # source-wide NBA original player XYZ versus human app heldout, not official promotion
    ".github/workflows/gamepulse-igp-p4-human-app-heldout-fusion-v31.yml",  # existing human labelled NBA app heldout vs single IGP Fusion, original source private only
    ".github/workflows/gamepulse-igp-g1-three-more-original-native-games.yml",  # 3 private source original NBA 13part selected actor keyframe upstream flag QA, aggregates only
    ".github/workflows/gamepulse-public-nba-touch-season-mirror-20261031.yml",  # public NBA season-level tracking mirror source SHA and private QA, aggregate public logs only
    ".github/workflows/gamepulse-nba-touch-official-source-probe-20261031.yml",  # source-only public NBA Stats player touch/paint endpoint diagnostic with safe status metadata
    ".github/workflows/gamepulse-igp-touch-v4-quality-sweep-20261031.yml",  # original private NBA 0138 player custody quality and time QA, aggregate-only
    ".github/workflows/gamepulse-igp-touch-v3-clock-control-sweep-20261031.yml",  # source SHA-pinned private NBA clock custody touch sensitivity, aggregate only
    ".github/workflows/gamepulse-igp-definition-aligned-touch-v2-rockets-20261031.yml",  # private source original NBA Rockets Bucks definition-aligned touch QA with public safe metrics only
    ".github/workflows/gamepulse-igp-v31-halfcourt-touch-rockets-research.yml",  # source-SHA pinned private-only v3.1 Rockets halfcourt touch QA; public safe totals only
    ".github/workflows/gamepulse-igp-fusion-g1-original-upstream-integrated-query.yml",  # P4 original SDK selected actor upstream keyframe flags as immutable optin single IGP Fusion layer
    ".github/workflows/gamepulse-igp-p4-g1-upstream-stratified-ball-holdout.yml",  # private original 13part actor provenance NBA source masked ball 3D holdout, aggregate only
    ".github/workflows/gamepulse-igp-g1-original-actor-upstream-provenance-0001.yml",  # private SHA verified original 13part raw SDK player ball interpolation provenance, aggregate logs only
    ".github/workflows/gamepulse-igp-p4-video-clock-blind-holdout.yml",  # original NBA independent broadcast held-out video labels vs private companion timing and metadata QA
    ".github/workflows/gamepulse-igp-p4-video-source-clock-joined.yml",  # original NBA private Broadcast+SDK P4 joined physical evidence, public aggregate only
    ".github/workflows/gamepulse-igp-p4-broadcast-vs-sdk-clock.yml",  # original private NBA SDK Time#show matched independent Broadcast scoreboard, aggregates only
    ".github/workflows/gamepulse-igp-p4-detroit-dense-broadcast-frames.yml",  # original authenticated NBA Broadcast video 0.5s review private only
    ".github/workflows/gamepulse-igp-fusion-p4-independent-video-possession.yml",  # private SHA-verified independent NBA Broadcast JPEG P4 possession research QA, public aggregate only
    ".github/workflows/gamepulse-igp-fusion-v3-68game-integration.yml",  # official source SHA 68game private research fusion entrypoint and public aggregate QA
    ".github/workflows/gamepulse-igp-p3-sourcegrade-v3-all68-query.yml",  # original NBA all68 source grade read-only QA, private values public counts only
    ".github/workflows/gamepulse-igp-p3-fastball-external8-replication.yml",  # third disjoint 8game original NBA ball source mask QA, source private
    ".github/workflows/gamepulse-igp-p3-fastball-sourcegrade-v3-readback.yml",  # original NBA SDK private short-ball provenance grade; public aggregates only
    ".github/workflows/gamepulse-igp-p3-ball-natural-600ms-matched.yml",  # original NBA <=600ms P3 ball masked source validation; public aggregate only
    ".github/workflows/gamepulse-igp-p3-physics-all68-natural-shadow.yml",  # private original 68 NBA full-native scene candidate source audit; safe totals only
    ".github/workflows/gamepulse-igp-p3-physics-fastball-shadow-v2.yml",  # private original NBA dual research hypotheses; public aggregates only
    ".github/workflows/gamepulse-igp-p3-ball-physics-dev16-unseen8.yml",  # SHA-pinned original NBA private source, aggregate research QA only
    ".github/workflows/gamepulse-igp-p3-fastball-shadow-query-readback.yml",  # private SHA-original 68-game NBA query candidate readback; only safe aggregates public
    ".github/workflows/gamepulse-igp-p3-fastball-16game-masked.yml",  # sixteen original-source NBA fast-ball masked validation; public aggregates only
    ".github/workflows/gamepulse-igp-p3-ball-speed-native68-qa.yml",  # SHA-private NBA ball speed source gap and masked original holdout aggregates only
    ".github/workflows/gamepulse-igp-p3-top3-native-ball-episodes.yml",  # original private NBA top3 natural 10Hz ball event episodes; aggregate public QA only
    ".github/workflows/gamepulse-igp-p3-pbp-shot-blackout-v1.yml",  # original NBA full11 masked PBP shooter contextual model; private source and QA only
    ".github/workflows/gamepulse-igp-p3-all68-natural-event-gap-atlas.yml",  # Private 68 original NBA PBP and 10Hz source hole attribution, public aggregates only
    ".github/workflows/gamepulse-igp-p3-joint-external-risk-v1.yml",  # P3 four unseen NBA full11 original source masks; private receipts and aggregate logs only
    ".github/workflows/gamepulse-igp-p3-joint-all11-handler-blackout-v1.yml",  # SHA-private original all11 blackout; public aggregate QA, private licensed source only
    ".github/workflows/gamepulse-igp-p3-whole-scene-original-2p4s-mask-v1.yml",  # P3 original 11-actor whole-scene source blackout; public aggregate only
    ".github/workflows/gamepulse-igp-p3-all68-one-sided-scene-shadow-v1.yml",  # private original 68-game NBA source scene shadow; public aggregate only
    ".github/workflows/gamepulse-igp-p3-fourgame-one-sided-shadow-v1.yml",  # private source SHA real incomplete NBA scenes, counts only
    ".github/workflows/gamepulse-igp-p3-handler-original-source-acceptance-v1.yml",  # original NBA private P3 handler eight-unseen no-promotion release check
    ".github/workflows/gamepulse-igp-p3-one-sided-peer-player-v1.yml",  # P3 original-NBA source one-sided masked player peer-context pilot
    ".github/workflows/gamepulse-igp-p3-all68-source-gap-census-v1.yml",  # NBA private 68-game original live actor source gap classification; aggregate public
    ".github/workflows/gamepulse-igp-p3-frozen-handler-eight-unseen-v1.yml",  # SHA-private NBA P3 ball handler eight unseen frozen 50 percent QA; aggregate only
    ".github/workflows/gamepulse-igp-p3-one-sided-duration-curve-v1.yml",  # SHA private NBA P3 causal one-sided mask 600-2400ms frozen model accuracy curve
    ".github/workflows/gamepulse-igp-p3-handler-frozen-confirmation-v1.yml",  # independent 4-game source-locked P3 handler w0.5 confirmation, aggregate only
    ".github/workflows/gamepulse-igp-p3-one-sided-eighttrain-eightunseen-v1.yml",  # private original NBA P3 causal one-sided source gap eight train/eight heldout
    ".github/workflows/gamepulse-igp-p3-new-handler-ball-anchor-v1.yml",  # SHA-private P3 source-ball peer-handler hypothesis; aggregate-only public logs
    ".github/workflows/gamepulse-igp-p3-sixteengame-eighttrain-eightunseen-v1.yml",  # original private NBA P3 8train/8unseen fixed source QA; aggregate only
    ".github/workflows/gamepulse-igp-p3-ball-context-source-acceptance-v1.yml",  # P3 crossgame ball model private SDK QA receipts; public only aggregate score
    ".github/workflows/gamepulse-igp-p3-ten-game-fresh-context-holdout-v1.yml",  # source-original P3 six train / four new heldout NBA games, aggregate QA only
    ".github/workflows/gamepulse-igp-p3-frozen-eightgame-external-source-validation-v1.yml",  # original private NBA eight unseen P3 crossgame frozen-model QA, aggregate only
    ".github/workflows/gamepulse-igp-p3-multiagent-crossgame-source-blackout-v1.yml",  # private SHA NBA four-game P3 cross-game source masks; aggregate-only public QA
    ".github/workflows/gamepulse-igp-p2-original-source-negative-acceptance-v1.yml",  # source-locked P2 four-game negative research decision; aggregate only
    ".github/workflows/gamepulse-igp-p2-original-mask-uncertainty-frontier-v1.yml",  # original private SDK P2 uncertainty/abstention QA, aggregate only
    ".github/workflows/gamepulse-igp-p2-fourgame-masked-method-comparison-v1.yml",  # private four-game source blackout direct-model comparison; public aggregate QA only
    ".github/workflows/gamepulse-igp-p2-fourgame-contiguous-gap-pilot-v1.yml",  # approved private SHA original NBA P2 source blackouts; public coverage-only
    ".github/workflows/gamepulse-igp-68-priority1-source-audit-release-gate-v1.yml",  # private SHA original source P1 five-game audited release gate; only aggregate public
    "tools/licensed_feed/igp_p1_0122_bounded_original_sdk_recheck.mjs",  # source-only SDK bounded 0122 recheck, licensed content private
    ".github/workflows/gamepulse-igp-0122-original-source-p1-two-part-recheck.yml",  # private original NBA SDK 0122 two-part reacquisition, aggregate only
    ".github/workflows/gamepulse-igp-68-p1-sparse-native-cadence-audit-v1.yml",  # SHA private NBA 3-game source cadence QA; no raw XYZ, public aggregate-only
    ".github/workflows/gamepulse-igp-0122-source-identity-gap-diagnostic-v1.yml",  # private SHA 0122 identity and native gap diagnosis; public aggregate-only
    ".github/workflows/gamepulse-igp-0092-approved-booker-source-alias-ab-v1.yml",  # approved game-only source ID correction: private SHA-backed A/B, aggregate QA only
    ".github/workflows/gamepulse-igp-68-priority1-source-triage-v1.yml",  # SHA-private 68-game existing receipt outlier audit; aggregate-only public logs
    ".github/workflows/gamepulse-igp-68-live-gap-census-v1.yml",  # pinned private all68 gap QA; public aggregate counts only
    ".github/workflows/gamepulse-igp-68-live-play-tracking-qa.yml",  # SHA-pinned private all68 clock-running metrics; public aggregate status only
    ".github/workflows/gamepulse-igp-68-continuous-possession-readback.yml",  # SHA-pinned private 68-game PBP readback; public aggregate status only
    ".github/workflows/gamepulse-igp-68-continuous-scene-v1.yml",  # SHA-pinned private 68-game source reconstruction; public aggregate counts only
    ".github/workflows/gamepulse-igp-close4-defender-xfg-68-current.yml",  # SHA-only private 68-game NBA source defender ranking, public aggregate results
    ".github/workflows/gamepulse-igp-gap4-xyz-shot-geometry.yml",  # private SHA-verified original-player geometry at NBA shot-event UTC; aggregate-only public QA
    ".github/workflows/gamepulse-igp-oct30-four-biomechanics-source-gap-recovery.yml",  # private original SDK 0142/0143 and official Blueprint 0143 re-read, public aggregate only
    ".github/workflows/igp-0129-user-clip-semantic-private-qa.yml",  # source SHA private clip/PBP QA; aggregate-only public logs
    ".github/workflows/gamepulse-igp-68-native-index-hourly.yml",  # scheduled private SHA original tracking and official NBA chain reindex, no public coordinates
    ".github/workflows/gamepulse-igp-68-native-index-refresh.yml",  # private accepted NBA 68-game original XYZ and per-possession source-index QA
    ".github/workflows/gamepulse-igp-native-scene-batch-qa.yml",  # private SHA original XYZ 480-frame readback; public aggregate only
    ".github/workflows/gamepulse-igp-native-scene-side-limit57.yml",  # private SHA 57-game source-proxy short-gap comparison; aggregate output only
    ".github/workflows/gamepulse-igp-68-native-scene-query-readback.yml",  # source-only original player/ball SHA private query QA with aggregate-only public output
    ".github/workflows/gamepulse-igp-oct28-existing-13parts-materialize.yml",  # reviewed SHA-native-only 0136/0137 private 13part source materialization, no public XYZ
    ".github/workflows/gamepulse-igp-68-native-low-rate-recovery.yml",  # source-only 11-game original SDK archive recovery; private SHA data only, no public XYZ
    ".github/workflows/gamepulse-igp-native-scene-season68-benchmark.yml",  # SHA-private 68-index and 57-original-game source-only aggregate QA, no licensed XYZ publicly
    ".github/workflows/gamepulse-igp-0138-native-scene-model.yml",  # reviewed private-only SHA-pinned 0138 holdout; public logs aggregate-only
    ".github/workflows/gamepulse-integrated-autocapture.yml",  # automated original NBA game-to-private-SHA canonical integration; public metadata counts only
    "tools/licensed_feed/igp_complete_season_plan.mjs",  # official fixture-only dynamic season planner; private SHA catalog readback, no raw records
    ".github/workflows/gamepulse-igp-oct28-twelve-nba-logical-chains.yml",  # only private original NBA PBP logical chains and SHA index outputs
    ".github/workflows/gamepulse-igp-oct28-blueprint-12-rich-source.yml",  # public official NBA original rich Blueprint reports, committed only private
    ".github/workflows/gamepulse-igp-oct28-eleven-native-recovery.yml",  # authenticated 11-game private SDK native 13-part recovery and SHA acceptance only
    ".github/workflows/gamepulse-igp-oct28-eleven-original-companion.yml",  # authorized original SDK companion captures saved privately, public counts only
    ".github/workflows/gamepulse-igp-post56-oct28-unified-qa.yml",  # private SHA-only 12-game additive validation; public aggregate logs only
    ".github/workflows/gamepulse-igp-0138-official-substitution-ten-v3.yml",  # Private NBA PBP starter substitution clock replay on 206 0138 possessions; withheld official ten QA
    ".github/workflows/gamepulse-igp-0138-possession-lineup-recovery-v2.yml",  # Private exact-ten source majority and no-substitute neighbor recovery for remaining 0138 PBP chains
    ".github/workflows/gamepulse-igp-0138-official-ten-possession.yml",  # SHA-verified full-game official NBA starters/substitution ten by logical possession private-only
    ".github/workflows/gamepulse-igp-0138-native-scene-holdout.yml",  # Source-locked 0138 whole-game provisional ten-player reconstruction/holdout private only
    ".github/workflows/gamepulse-igp-0138-video-utc-source-window.yml",  # Private original native Q1 2:52 source UTC bracket for independent app marker alignment
    ".github/workflows/gamepulse-igp-0138-advanced-join.yml",  # Existing private canonical source-locked 176-shot advanced additive ledger and smoke-query QA
    ".github/workflows/gamepulse-igp-0138-blueprint-source.yml",  # Original official NBA Blueprint 0138 shot xFG/defender/gravity private-only SHA receipt
    ".github/workflows/gamepulse-igp-0138-advanced-source.yml",  # Private-only full companion ShotDetails/Time/OnCourt/insights source; aggregate public QA
    ".github/workflows/gamepulse-igp-0138-native-index-qa.yml",  # Single-game SHA-private native index and masked-source QA; no licensed public data
    ".github/workflows/gamepulse-igp-0138-fullgame-recovery.yml",  # Narrow reviewed private NBA original source 0138 recovery; aggregate-only public output
    ".github/workflows/gamepulse-pr776-raised-hand-defender-jump-all56.yml",  # SHA-private 56-game shot height/jump descriptive analysis; aggregate QA only
    ".github/workflows/freeview-amen732-sixview-gaussian-model-input-preflight.yml",  # only private source input artifacts, public stage/status counts
    "tools/amen732_genuine_sixview_gaussian_preflight.py",  # six locked original source SHA, no public licensed image pixels
    ".github/workflows/freeview-amen732-blackwell-access-preflight.yml",  # no-cost IAM/read-only GPU route check; no NBA source input published
    ".github/workflows/freeview-amen732-archive-to-current-pixel-crosswalk.yml",  # source pixels private/ephemeral, camera-matching metrics public only
    "tools/amen732_archive_fresh_visual_correspondences.py",  # private original vs fresh pixel matching, never source media in public repo
    ".github/workflows/gamepulse-igp-post36-official-native-player-slot-qa.yml",  # reviewed: private 20-game original NBA source and frozen36 read-only verification; aggregate public logs only; no artifacts
    ".github/workflows/gamepulse-igp-post36-unlinked-identity-triage.yml",  # 20-game SHA-private native unlinked official-ten/source-ball diagnostic with aggregate-only public logs
    ".github/workflows/gamepulse-igp-post36-official-ten-pbp-native-evidence-qa.yml",  # private source NBA box + PBP substitution official-ten native identity 20-game QA, aggregates only
    ".github/workflows/gamepulse-igp-g4-all56-native-possession-product-qa.yml",  # full 56 private NBA real source native possession readback and action/shot QA, safe aggregates
    ".github/workflows/gamepulse-igp-g4-post36-all56-real-index.yml",  # SHA-private 20 original native games G4 logical chain additive index, aggregate logs only
    ".github/workflows/gamepulse-pr776-defensive-biomech-all56.yml",  # concurrent private-only original-shot biomech QA; no original licensed coordinates in runner logs
    ".github/workflows/gamepulse-pr776-defensive-biomech-all56.yml",  # read-only SHA-verified private NBA shot analysis, aggregate QA committed private; no raw coordinates
    ".github/workflows/gamepulse-igp-possession-search-product-real-qa.yml",  # private G4/native possession + all56 unified search real source QA; public safe aggregates
    ".github/workflows/gamepulse-igp-5s-multiscale-native-eightgame.yml",  # private 5s withheld actor trajectory six train two test SHA source-only QA
    ".github/workflows/gamepulse-igp-original-five-second-team-identity-v2.yml",  # original NBA official team exclusions from 18 source long-gap ID hypotheses, aggregate-only QA
    ".github/workflows/gamepulse-igp-original-five-second-alias-continuity.yml",  # private SHA original NBA gap actor overlap and endpoint diagnostics, no private XY logs
    ".github/workflows/gamepulse-igp-natural-5s-source-alias-audit.yml",  # all36 private original-source native five-second extra-player alias hypotheses; no licensed coordinates
    ".github/workflows/gamepulse-igp-5s-native-risk-holdout-8game.yml",  # SHA-private source-native five-second masked motion-envelope risk gate and heldout aggregate evaluation
    ".github/workflows/gamepulse-igp-5s-peer-scene-warp-real-source.yml",  # private SHA NBA 5s other-player/ball source-only trajectory QA; no licensed coordinates in public logs
    ".github/workflows/gamepulse-igp-native-C0-full36-coverage.yml",  # SHA-verified private NBA native strict official-ten sample coverage, public only aggregate counts
    ".github/workflows/gamepulse-igp-sixgame-crossvalidate-velocity.yml",  # reproducible private source SHA NBA trajectory holdouts, only aggregate error metrics publicly
    ".github/workflows/gamepulse-igp-native-bounded-velocity-query-qa.yml",  # private original SDK SHA read-only query regression; aggregate only never source coordinates
    ".github/workflows/gamepulse-igp-cross-game-native-mask-challenger.yml",  # guarded SHA-original private NBA blocked XYZ holdout; only aggregate p50/p95/p99 in public logs
    ".github/workflows/gamepulse-igp-source-shot-utc-guard-qa.yml",  # private 54-source shot UTC guard SHA query readback, original data and coordinates never public
    ".github/workflows/gamepulse-igp-shot-start-lineup-paired-54.yml",  # private SHA-verified NBA source shot/start identity evidence; public only aggregated QA counts
    ".github/workflows/gamepulse-igp-six-shooter-lineup-dossier.yml",  # private original NBA app and official PBP source-verified identity discrepancy QA; aggregate public logs only
    ".github/workflows/gamepulse-igp-clock-grade-query-readback.yml",  # reviewed private SHA-only NBA clock/action readback and safe aggregate log; no licensed coordinates
    ".github/workflows/gamepulse-igp-54game-clock-lineup-crosscheck.yml",  # SHA-verifies 54 original NBA companion packages against official shots; private QA only, aggregate logs
    ".github/workflows/gamepulse-igp-companion-pbp-clock-agreement-v1.yml",  # private original NBA companion/PBP clock diagnostics only, no public licensed data
    ".github/workflows/gamepulse-igp-companion-pbp-clock-agreement-v1.yml",  # reviewed: source SHA preserved, private-only 54-game NBA clock/PBP grade partitions, aggregate public log, no licensed coordinates
    ".github/workflows/gamepulse-igp-54companion-app-index-qa.yml",  # private stored original NBA app event source indexing; only aggregate counts public
    ".github/workflows/gamepulse-igp-0006-companion-original-retry.yml",  # authorized original SDK 0006 companion source recovery retry, original payload remains private
    ".github/workflows/gamepulse-igp-all56-companion-app-packages-and-bio-v2.yml",  # source-verified private 56-game full app packages plus precise shot-feature join; only QA aggregates public
    ".github/workflows/gamepulse-igp-companion-two-sdk-availability-repair.yml",  # retry two verified timeout source SDK sessions, original data private
    ".github/workflows/gamepulse-igp-all56-advanced-source-biomechanics-acceptance.yml",  # full56 private SDK source shot identity join, no licensed public records
    ".github/workflows/gamepulse-igp-advanced-original-shots-v2-smoke.yml",  # private source-identity test, aggregate count only
    ".github/workflows/gamepulse-igp-companion-54game-shot-details-capture.yml",  # authorized SDK original 54-game event JSON to private 104 only; no licensed content publicly
    "tools/licensed_feed/companion_original_sdk_probe.mjs",  # reviewed private-only shot original source recovery and source-graded QA
    ".github/workflows/gamepulse-igp-companion-full-events-licensed-probe.yml",  # reviewed private-only shot original source recovery and source-graded QA
    ".github/workflows/gamepulse-igp-all56-shot-biomechanics-native-materialize.yml",  # reviewed private-only shot original source recovery and source-graded QA
    ".github/workflows/gamepulse-igp-0131-late-full56-model-v3.yml",  # upgrade only source-authenticated 0131 late model, preserve 55 immutable private models
    ".github/workflows/gamepulse-igp-0131-8part-original-merge.yml",  # 7 original SHA Release parts plus one original SHA private Git SDK, materialized private only
    ".github/workflows/gamepulse-igp-oct27-0131-late-original-direct-git.yml",  # original authenticated NBA 0131 late SDK window, SHA private commit only
    ".github/workflows/gamepulse-igp-unified-56-two-real-source-recovery-model.yml",  # two original seven-part SDK sources modeled privately, SHA preserved, aggregate counts public
    ".github/workflows/gamepulse-igp-oct27-seven-part-original-xyz-recovery.yml",  # authentic 7-part SHA private NBA original XYZ recovery only, public counts, never source positions
    ".github/workflows/gamepulse-igp-unified-56-private-query-qa.yml",  # private-original SHA-checked unified query only, public aggregate status, no coordinates

    ".github/workflows/gamepulse-igp-unified-56-season-tracking.yml",  # private NBA XYZ / models / Blueprint SHA verification and unified private QA only; public counts and status, no private XYZ
    ".github/workflows/gamepulse-igp-blueprint-official-56-qa.yml",  # SHA-only NBA public Blueprint shots versus private official PBP aggregate QA
    ".github/workflows/gamepulse-ippt-oct27-blueprint-backfill.yml",  # NBA public original shot report to private research branch only
    ".github/workflows/gamepulse-official-pbp-post36-backfill.yml",  # official public NBA PBP/box bytes committed private with final-score QA
    ".github/workflows/gamepulse-companion-original-0129-pilot.yml",  # bounded unauthenticated source GET; original bytes private release, public status only
    ".github/workflows/gamepulse-pr776-rockets-companion-z-variant-qa.yml",  # private SHA-verified NBA original SDK keyframe variant aggregate QA only; never public XYZ or licensed source artifacts
    ".github/workflows/gamepulse-ippt-public-web-app-shot-response-discovery.yml",  # first-party NBA public web endpoint structural shot-field check only; no auth, cookies, query URLs, raw payloads
    "tools/licensed_feed/public_web_shot_response_probe.mjs",  # first-party NBA public web endpoint structural shot-field check only; no auth, cookies, query URLs, raw payloads
    ".github/workflows/gamepulse-ippt-app-shot-details-0022600129-blueprint.yml",  # official public NBA Blueprint DET-NYK screenshot exact-shot attribute and precision check, private report
    ".github/workflows/gamepulse-ippt-app-shot-transmit-original-0125.yml",  # original authenticated private GamePulse EaseLive SDK shot-event JSON schema (structure only)
    ".github/workflows/gamepulse-ippt-public-stat-release-gate-2026.yml",  # no original NBA XYZ; private QA-driven public-stat fail-closed publication gate
    ".github/workflows/freeview-amen732-six-camera-real-native-synced-video.yml",  # six original NBA source cameras, UHD output to private 104 only
    "tools/amen732_sixview_synchronous_video_review_v1.py",  # ephemeral native source exact 4K mosaic, private output only
    ".github/workflows/freeview-amen732-original-vs-reacquired-source-sha.yml",  # compare six original NBA private release native MP4 identities, SHA-only
    ".github/workflows/freeview-amen732-private-synced-panel-review-readback.yml",  # private already SHA-verified source panel preview, no public source frames
    ".github/workflows/freeview-amen732-sixview-audio-corrected-contact-sheet.yml",  # SHA original six source feeds, private 4K native panels only
    "tools/amen732_sixview_native_frame_package_v2.py",  # ephemeral source original native PNG crops, no public pixels
    ".github/workflows/freeview-amen732-sixview-physical-sync-audit.yml",  # six native MP4 audio/timing audit: NO licensed media in public artifact
    "tools/amen732_sixview_audio_alignment_v2.py",  # hashed source manifest and source timestamp only
    ".github/workflows/gamepulse-ippt-clock-ten-model-all36.yml",  # private exact original NBA gameclock ten-player and ball model materialized, public aggregate QA only
    ".github/workflows/gamepulse-ippt-official-clock-model-real-2games.yml",  # private exact SHA NBA official ten full XYZ model physical-time query pilot aggregate QA
    ".github/workflows/gamepulse-ippt-official-gameclock-ten-36.yml",  # private original NBA official ten gameclock model source bracket QA, aggregate only
    ".github/workflows/gamepulse-ippt-running-gameclock-source-36.yml",  # private NBA official clock-progressing source coverage, no source player XYZ public
    ".github/workflows/gamepulse-ippt-possession-searchability-36.yml",  # private NBA source original PBP chain-searchability denominator QA; aggregate counts only
    ".github/workflows/gamepulse-ippt-model-b-native-graded-tiers-all36.yml",  # private source SHA G4 ten actor tiered ModelB coverage and ball aggregate QA only
    ".github/workflows/gamepulse-ippt-model-b-native-all36-private.yml",  # private SHA original NBA G4 source Model B overlay all36 actual performance/coverage, aggregate logs only
    "tools/amen732_native_sixvideo_fusion_mp4.py",  # reviewed original NBA event-732 direct six-view model-only research
    "tools/amen732_da3_unposed_sixview_trial.py",  # reviewed original NBA event-732 direct six-view model-only research
    "tools/amen732_native_six_video_frame_sets.py",  # reviewed original NBA event-732 direct six-view model-only research
    "tools/amen732_official_sixvideo_acquire.py",  # reviewed original NBA event-732 direct six-view model-only research
    ".github/workflows/freeview-amen732-direct-sixvideo-render.yml",  # reviewed original NBA event-732 direct six-view model-only research
    "tools/amen732_freeview_sixvideo_public_source.py",  # public NBA source ephemeral 6-video scene only; private MP4 sink
    ".github/workflows/freeview-amen732-sixvideo-public-reacquire.yml",  # official public source fallback with private result
    ".github/workflows/freeview-amen732-official-sixstream-source-probe.yml",  # Official public NBA six-stream probe; no private release or artifacts
    ".github/workflows/freeview-amen732-release-auth-bypass-probe.yml",  # private source access over direct release CDN, no public data
    ".github/workflows/freeview-amen732-six-original-videos-merged-private.yml",  # six private NBA source clips ephemeral, UHD merged MP4 private release only
    ".github/workflows/freeview-amen732-six-native-video-fusion.yml",  # private-only six-MP4 3D fusion and MP4 output
    ".github/workflows/gamepulse-ippt-source-ten-coverage-all36.yml",  # private SHA G4 native source-anchored ten plus ball outside official roster G2; aggregate QA only
    ".github/workflows/gamepulse-ippt-empty-chain-source-lag-tiers-36.yml",  # original NBA G4 SHA exact scorer-UTC nearest source lag tier for 129 unresolved chains private QA, public aggregates only
    ".github/workflows/freeview-amen732-da3-private-qa-readback.yml",  # SHA-verifies DA3 release results and commits only to private 104
    ".github/workflows/gamepulse-ippt-native-409-chain-coverage-36.yml",  # original NBA G4 36-game SHA source per-slot, ball, all-native chain-second and empty-chain aggregate private QA; public counts only
    ".github/workflows/freeview-amen732-da3-private-unposed-cpu.yml",  # private-only six-view CPU inference; model/source/output not published in public repo
    ".github/workflows/gamepulse-ippt-full-native-possession-v1-integration.yml",  # original 36-game G4 full native + v3 PBP source private read-only QA only; no private XYZ or actor IDs public
    ".github/workflows/gamepulse-ippt-all-event-sqlite-private-git.yml",  # private Git transport persist original NBA XY SQLite to separate private branch
    ".github/workflows/gamepulse-ippt-all-event-sqlite-private-release.yml",  # publish original NBA actor XY DB to PRIVATE repo release only; no public artifacts
    ".github/workflows/gamepulse-ippt-all-event-sqlite-private.yml",  # original all-action NBA source XY private-only SQLite, public count QA only
    ".github/workflows/gamepulse-ippt-private-v3-event-source-physics-sqlite.yml",  # private licensed original NBA PBP candidate XY + video-unverified moments only
    ".github/workflows/gamepulse-ippt-all-event-motion-v3-query-qa.yml",  # all22k private PBP XY/causal/motion readonly search full-index QA
    ".github/workflows/gamepulse-ippt-all-event-source-motion-v3-private.yml",  # exact SHA private NBA PBP original XY source candidate SQLite, no public binary
    ".github/workflows/gamepulse-ippt-native-event-physics-source-36.yml",  # original NBA shot and rebound source time candidate research only; no private XYZ in public logs
    ".github/workflows/gamepulse-ippt-private-v2-native-xy-causal-sqlite.yml",  # private original PBP native XY v2 causal graph immutable v1 + private DB
    ".github/workflows/gamepulse-ippt-all-pbp-causal-bundles.yml",  # PBP source all event scorer UTC causal graph aggregates only
    ".github/workflows/gamepulse-ippt-rebound-fourway-native-crosscheck.yml",  # all36 original NBA rebound native label/PBP/ball/official ten private-aggregate QA
    ".github/workflows/gamepulse-ippt-native-lasttouch-all-pbp-36.yml",  # original SHA native fresh label PBP actor identity aggregate crosscheck
    ".github/workflows/gamepulse-ippt-all10-rebound-contrastive-36.yml",  # source-only original NBA ball/official ten rebound rank aggregate diagnostics
    ".github/workflows/gamepulse-ippt-rebound-control-source-hypothesis.yml",  # private SHA original nonshot physics / wrong actor control aggregate only
    ".github/workflows/gamepulse-ippt-sdk-native-clock-schema.yml",  # exact SHA original SDK time/period metadata presence only; private source no values
    ".github/workflows/gamepulse-ippt-all-pbp-native-xy-36.yml",  # all22,314 original NBA PBP action XY read-only private SHA aggregate-only
    ".github/workflows/gamepulse-ippt-blueprint-shot-release-query.yml",  # exact NBA event source and published original Blueprint private aggregate QA
    ".github/workflows/gamepulse-ippt-blueprint-source-release-36-query.yml",  # SHA private NBA read-only event query aggregate acceptance only
    ".github/workflows/gamepulse-ippt-blueprint-pbp-shotchart-lineage-36.yml",  # SHA original public NBA PBP vs official Blueprint chart XY aggregate equality only
    ".github/workflows/gamepulse-ippt-blueprint-location-xy-30-holdout.yml",  # published Blueprint chart vs original shooter XY aggregate QA
    ".github/workflows/gamepulse-ippt-all36-original-sdk-actor-flags.yml",  # six shard original NBA SDK actor native event flag QA
    ".github/workflows/gamepulse-ippt-raw-sdk-event-interpolation-provenance.yml",  # source raw SDK per-actor interpolation flag QA
    ".github/workflows/gamepulse-ippt-native-pose-provenance-schema.yml",  # audited original NBA native pose and interpolation flags aggregate-only
    ".github/workflows/gamepulse-ippt-event-native-coordinate-masked-36.yml",  # original NBA shot event XY ball3D validation aggregate-only
    ".github/workflows/gamepulse-ippt-blueprint-geometry-definition.yml",  # original-source NBA event geometry QA only
    ".github/workflows/gamepulse-ippt-blueprint-common-delay-36.yml",  # source-only Blueprint event alignment aggregates
    ".github/workflows/gamepulse-ippt-blueprint-shot-release-query.yml",
    ".github/workflows/gamepulse-ippt-shot-release-30game-holdout.yml",  # vetted event QA workflow
    ".github/workflows/gamepulse-ippt-ball-shot-release-candidate.yml",  # private original ball-shooter shot-release source motion and aggregate Blueprint comparison only
    ".github/workflows/gamepulse-ippt-blueprint-event-offset-diagnostic.yml",  # private source scorer UTC offset consistency, aggregates only
    ".github/workflows/gamepulse-ippt-blueprint-event-geometry-36.yml",  # private official NBA Blueprint release-distance benchmark, aggregate summaries only
    ".github/workflows/gamepulse-ippt-event-source-holdout.yml",  # reviewed original source frame blackout: aggregate error only, no licensed native XYZ
    ".github/workflows/gamepulse-ippt-event-snapshot-query-qa.yml",  # reviewed private SHA NBA event-source query, aggregate QA only, no private original XYZ
    ".github/workflows/gamepulse-ippt-event-snapshot-36-census.yml",  # reviewed original NBA PBP event join: aggregate source/ID/timing only, no private XYZ
    ".github/workflows/gamepulse-ippt-v03-four-game-holdout.yml",  # reviewed 4 private SHA NBA source games, p95/errors only, never player XYZ
    ".github/workflows/gamepulse-pr776-four-foot-defended-release-gravity.yml",  # private-only accepted Blueprint four-foot contested shooting with SHA-verified Gravity QA
    ".github/workflows/gamepulse-ippt-halfcourt-challenger-v03.yml",  # reviewed original NBA source masked QA, aggregate error only never XYZ
    ".github/workflows/gamepulse-pr776-six-foot-defended-release-gravity.yml",  # private-only accepted shot releases filtered by Blueprint contest distance <=72 inches, QA private
    ".github/workflows/gamepulse-ippt-halfcourt-settled-v2.yml",  # reviewed private source 36-game aggregate only; licensed NBA XYZ never logged
    ".github/workflows/gamepulse-ippt-halfcourt-offense-defense-qa.yml",  # reviewed private SHA NBA source, aggregate only official five cardinalities, no XYZ
    ".github/workflows/gamepulse-ippt-halfcourt-dual-benchmark.yml",  # reviewed private SHA NBA source, only aggregated selector/coverage counts; no licensed XYZ public
    ".github/workflows/gamepulse-ippt-isolated-source-pilot.yml",  # reviewed private-only aggregate CPU workflow
    ".github/workflows/gamepulse-ippt-isolated-source-pilot.yml",  # reviewed IPPT SHA private-source only; public logs game-level aggregate counts and holdout error percentiles, no player XYZ
    ".github/workflows/gamepulse-pr776-release-contest-gravity-joined.yml",  # read-only private Blueprint/Gravity SQLite, private-only aggregate and per-shot CSV outputs
    ".github/workflows/gamepulse-pr776-official-nba-season-gravity.yml",  # source-qualified public NBA Gravity leaders only; private SQLite and QA never published here
    "public_nba_gravity_leaders_2026_27_current.json",  # direct NBA public gravityleaders response with source SHA; no private XYZ
    ".github/workflows/gamepulse-pr776-blueprint-shot-gravity-52.yml",  # reviewed private licensed Blueprint source + PBP, public aggregate counts only, SQLite/QA committed private
    ".github/workflows/gamepulse-pr776-G4-native-player-possession-36.yml",  # reviewed 36-game G4 private SHA native actor, ball, NBA PBP chain indexing; no original XYZ in public logs
    ".github/workflows/gamepulse-pr776-G2-source-actor-transition-index-36.yml",  # private original NBA SDK substitution source player clock index, SHA-only public metrics
    "worker_results/reed-0022600125-q2-0841-temporary-multiangle.json",  # reviewed no licensed SDK XYZ, signed HLS or tokens; NBA public event metadata only
    ".github/workflows/resolve-reed-20261026-camera-angles.yml",  # reviewed signed NBA HLS URLs and exception details removed from public output
    ".github/workflows/gamepulse-pr776-G2-direct-actor-sub-transition-36.yml",  # SHA original NBA SDK roster change-source player observation clock analysis, safe aggregate public logs
    ".github/workflows/gamepulse-pr776-G2-exact-ten-transition-UTC-36.yml",  # original SDK source ten identity transition vs NBA official substitution UTC, aggregate-only public output
    ".github/workflows/gamepulse-pr776-G2-substitution-actor-query-36.yml",  # reviewed original private NBA actor/ball G1 SHA readback and pre/post-substitution G2 alternative roster, only safe public counts
    ".github/workflows/gamepulse-pr776-G2-substitution-source-identity-attribution-36.yml",  # G2 SHA-frozen NBA official substitution-side raw actor classification, private aggregate only
    ".github/workflows/gamepulse-pr776-G2-nba-substitution-side-query-36.yml",
    ".github/workflows/gamepulse-pr776-G2-substitution-side-roster-36.yml",
    ".github/workflows/gamepulse-pr776-G2-clock-source-conflict-dossier-36.yml",  # reviewed G2 private SDK source ID-to-official-NBA PBP/lineup forensic dossier, aggregate counts only public
    ".github/workflows/gamepulse-pr776-G2-source-official-conflict-episodes-36.yml",  # reviewed: private original SDK actor vs NBA official roster conflict episode QA, aggregate-only public output
    ".github/workflows/gamepulse-pr776-G2-roster-query-readbacks-36.yml",  # reviewed: 36 game private official NBA PBP long-pair roster source/G1 SHA readbacks, aggregate-only public output
    ".github/workflows/gamepulse-pr776-G2-long-official-pbp-roster-36.yml",  # reviewed: private SHA-verified NBA PBP two-ended longer UTC roster candidate QA, public aggregate counts only, no XYZ
    ".github/workflows/gamepulse-pr776-original-actor-G1-provenance-all36.yml",  # approved all-36 private raw SDK per-actor SHA+interpolation provenance, only safe aggregate public logs
    ".github/workflows/gamepulse-pr776-original-actor-G1-provenance-pilot.yml",  # reviewed: two SHA-verified private NBA SDK source games, actor interpolation metadata only; no public XYZ or player IDs
    ".github/workflows/gamepulse-pr776-full-native-P0-acceptance-36.yml",  # reviewed: SHA-verified private original-source 36-game XYZ readback; aggregate-only public logs, private QA receipt
    ".github/workflows/gamepulse-pr776-official-ten-source-conflict-36.yml",  # reviewed: private 36-game source/official strict NBA ten conflict metadata only, no public player coordinates
    ".github/workflows/gamepulse-pr776-source-first-B-reconciliation-36.yml",  # reviewed: frozen accepted QA manifests only, 36-game SHA-accounting aggregates written private
    ".github/workflows/gamepulse-pr776-original-sdk-interpolation-lineage-36.yml",  # reviewed: 36 SHA-verified 13-part original private SDK archives, per-game QA only committed to private PR, public runner logs aggregate counts
    ".github/workflows/gamepulse-pr776-original-sdk-metadata-fidelity-rockets.yml",  # reviewed: exact 13 SHA-verified private NBA SDK tarballs, metadata-only private QA, never public raw coordinates
    ".github/workflows/gamepulse-pr776-source-first-atlas-36.yml",  # reviewed: private original SDK source read-only; public logs contain aggregate status/counts, SHA-pinned QA committed private-only
    ".github/workflows/gamepulse-pr776-natural-original-player-gaps.yml",  # reviewed: SHA-verified private player direct-gap distribution, aggregate only, original XYZ not in public logs
    ".github/workflows/gamepulse-pr776-c1-5-8-10s-benchmark.yml",  # reviewed: read-only SHA-verified private NBA XYZ withheld eval, aggregate results private-only; no player locations in public logs
    ".github/workflows/gamepulse-igp-fast-lineup-two-game-qa.yml",  # private-only source ten-ID anchors and guarded 2–5s masked XYZ holdout; no public source or artifacts
    ".github/workflows/gamepulse-rockets-official-utc-overlap-graph.yml",  # reviewed private-only PBP UTC overlap graph; no coordinates or public artifacts
    ".github/workflows/gamepulse-rockets-xfg-chain-source-qa.yml",  # reviewed private-only SHA-pinned Blueprint xFG to official logical-chain QA, aggregate public logs
    ".github/workflows/gamepulse-rockets-original-frame-gap-attribution.yml",  # reviewed private-only SHA-checked original frame-window diagnostic, aggregate public logs
    ".github/workflows/gamepulse-oct26-official-pbp-public.yml",  # official NBA PBP source-only, private repo write through existing GitHub token
    ".github/workflows/gamepulse-oct26-last3-parallel-parts.yml",  # bounded original NBA SDK live-ended parts; private-only releases
    ".github/workflows/gamepulse-oct26-incremental-catalog.yml",  # private complete-source 43-to-52 incremental catalog indexer
    ".github/workflows/gamepulse-igp-additive-original-source-index.yml",  # private additive original XYZ 36-to-52 source manifest; no public raw XYZ
    ".github/workflows/gamepulse-oct25-26-original-xyz-catchup.yml",  # private original SDK Oct25-26 official final batch; no public source or artifacts
    ".github/workflows/gamepulse-private-season43-integrity.yml",  # reviewed: private sparse-source SHA acceptance, aggregate-only logs
    "tools/gamepulse_private_43_integrity_acceptance.py",  # reviewed: local SHA checks of licensed private views, no public data
    ".github/workflows/gamepulse-official-20261025-seven.yml",  # reviewed: official NBA seven-game PBP and advanced source private-only publication; no public artifacts
    ".github/workflows/gamepulse-pr776-realutc-chain-xyz-query.yml",  # reviewed SHA-guarded NBA real UTC chain source lookup, private coordinates only
    ".github/workflows/gamepulse-pr776-wallclock-native-possession-query.yml",  # reviewed private 36-game source UTC/native interval QA, metadata-only public stdout and private-only output
    ".github/workflows/gamepulse-pr776-rebound-video-recovery.yml",  # manually inspected: exact one-event P2 private NBA Broadcast media, SHA-only public status, no upload-artifact, source remains private
    ".github/workflows/gamepulse-pr776-wallclock-season-index-36.yml",  # reviewed: SHA-pinned private original 36-game frames, no public coordinates or artifacts
    ".github/workflows/gamepulse-pr776-original-xyz-timeactual-chain-36.yml",  # reviewed private 36-game original SDK source-to-PBP UTC candidate QA only
    ".github/workflows/gamepulse-pr776-timeactual-wall-36.yml",  # reviewed private official 36-game NBA timeActual + native manifests, public counts only
    ".github/workflows/gamepulse-pr776-official-wall-time-acceptance.yml",  # reviewed official NBA timeActual plus private SDK UTC QA, aggregates only publicly
    ".github/workflows/gamepulse-pr776-broadcast-anchor-video-access.yml",  # reviewed NBA official event-video endpoint access, metadata QA only, no clips
    ".github/workflows/freeview-amen732-board-static-sources.yml",
    ".github/workflows/freeview-amen732-multipt-photo-refit.yml",
    ".github/workflows/gamepulse-pr776-direct-sdk-time-probe.yml",  # reviewed one-game private source SHA metadata schema only; never publish raw SDK coordinates/values
    ".github/workflows/gamepulse-pr776-unified-chain-xyz-v2.yml",  # private-only NBA XYZ source evidence
    ".github/workflows/gamepulse-pr776-direct-full-sdk-120-fallback.yml",  # private immutable original full SDK source fallback with aggregate logs
    ".github/workflows/gamepulse-pr776-chain-queryable-28-qa.yml",  # private SHA-verified aggregate original XYZ only
    ".github/workflows/gamepulse-pr776-chain-xyz-query-pilot.yml",  # private-only source-indexed 10-player/ball query; aggregate log without raw XYZ
    ".github/workflows/gamepulse-pr776-monotone-native-28game.yml",  # reviewed: private SHA-checked native NBA chain research, only aggregate public logs
    ".github/workflows/gamepulse-pr776-monotone-native-chain-pilot.yml",  # private source XYZ only in ephemeral CPU; aggregate candidate evidence in private repo; public logs counts only
    ".github/workflows/gamepulse-pr776-physical-nba-candidate-36.yml",  # reviewed: SHA-checked private official NBA PBP, candidate metadata only, no raw XYZ or public artifacts
    ".github/workflows/gamepulse-pr776-physical-native-36-continuity.yml",  # reviewed: private-only 36-game SHA continuity QA; aggregate counts only, no public source outputs
    ".github/workflows/freeview-amen732-right-above-rim-metric.yml",
    ".github/workflows/freeview-amen732-static-right-above-rim.yml",
    ".github/workflows/freeview-amen732-high-tight-third-view.yml",
    ".github/workflows/freeview-amen732-left-long-research-pts.yml",
    ".github/workflows/freeview-amen732-two-slash-extended-native.yml",
    ".github/workflows/gamepulse-pr776-original-xyz-search-audit.yml",  # reviewed: private-only SHA-verified XYZ CPU acceptance
    ".github/workflows/gamepulse-pr776-event-episode-crosswalk-test.yml",  # reviewed pinned private-only CPU acceptance, no source publication
    ".github/workflows/freeview-amen732-sam2-world-camera-holdout.yml",
    ".github/workflows/freeview-amen732-sam21-23-source-frames.yml",
    ".github/workflows/freeview-amen732-43xyz-23pixel-holdout.yml",
    ".github/workflows/freeview-amen732-q4-sdk-proof.yml",
    ".github/workflows/freeview-amen732-sam21-cpu-masks.yml",
    ".github/workflows/amen732-cotracker3-source-research.yml",
    ".github/workflows/freeview-amen732-ball-evidence.yml",
    ".github/workflows/gamepulse-original-raw-completeness.yml",  # reviewed: SHA-pinned original source read-only aggregate QA, no raw data publication
    ".github/workflows/gamepulse-pr776-original-sdk-terminal-xyz.yml",  # reviewed: one real private NBA SDK game, original SHA, aggregate-only logs
    ".github/workflows/gamepulse-pr776-rockets-spurs-native-advanced.yml",  # reviewed: CPU, private original NBA source and private-only source publish
    ".github/workflows/gamepulse-pr776-season-search-provider-acceptance.yml",  # reviewed ephemeral private NBA source retrieval and aggregate-only QA
    ".github/workflows/gamepulse-pr776-acceptance-20261025.yml",  # reviewed CPU-only pinned SHA private fetch; no public data outputs
    ".github/workflows/gamepulse-wemby-defensive-position.yml",  # CPU-only original NBA source, private source/aggregated results only
    ".github/workflows/clip-lab-event80-direct-native-frozen.yml",  # audited CPU-only original NBA source, private SDK, final ringed MP4
    ".github/workflows/clip-lab-rockets-event80-frozen-render.yml",  # reviewed: exact frozen source SHA and private-only v3.1 MP4
    ".github/workflows/clip-lab-event80-delivery-smoke.yml",  # test fixture artifact only
    ".github/workflows/clip-lab-rockets-event80-hls.yml",  # reviewed: exact one-event private HLS CPU staging only
    ".github/workflows/clip-lab-rockets-event80-native.yml",  # reviewed: exact event native SDK SHA extraction, private only
    ".github/workflows/clip-lab-rockets-event80-frozen-cpu.yml",  # reviewed: original CPU frozen v3.1 detector, private QA only
    ".github/workflows/clip-lab-encrypted-event86-handoff.yml",
    "tools/clip_lab_public_handoff_cert.pem",
    ".github/workflows/clip-lab-artifact-handoff-smoke.yml",
    ".github/workflows/freeview-amen-732-4k-contact-diagnostic.yml",
    ".github/workflows/clip-lab-adams86-original-frozen-cpu-full20.yml",
    ".github/workflows/clip-lab-event86-view-quality-cpu.yml",
    ".github/workflows/clip-lab-adams86-xfg-source-quality.yml",
    ".github/workflows/clip-lab-adams86-original-frozen-cpu-tracker-probe.yml",
    ".github/workflows/clip-lab-rockets-spurs-adams-86-video-sync.yml",
    ".github/workflows/clip-lab-rockets-spurs-adams-86-native-video.yml",
    ".github/workflows/freeview-amen-732-final-seconds-recovery.yml",
    ".github/workflows/rockets-spurs-q1-sdk-recovery.yml",
    ".github/workflows/gamepulse-unresolved-official-onoff-watch.yml",
    "tools/licensed_feed/pbpstats_missing_onoff_fallback.py",
    ".github/workflows/gamepulse-pbpstats-missing-game-fallback.yml",
    ".github/workflows/gamepulse-28game-source-assemble.yml",
    ".github/workflows/gamepulse-28game-possession-tracking-crosswalk.yml",
    ".github/workflows/gamepulse-native-interactions-season-missing13.yml",
    ".github/workflows/gamepulse-two-game-chronology-acceptance.yml",
    ".github/workflows/gamepulse-universal-alignment-acceptance.yml",  # private-only CPU gate; universal source/clock/possession QA
    ".github/workflows/gamepulse-video-free-clock-season.yml",  # source-only daily CPU backfill; no video, no public player assets
    ".github/workflows/gamepulse-nba-official-advanced-ratings.yml",
    ".github/workflows/clip-lab-rockets-event80-hls.yml",
    ".github/workflows/gamepulse-native-interactions-partial-aggregate.yml",
    ".github/workflows/gamepulse-season-query-coverage-tests.yml",
    ".github/workflows/gamepulse-quarantined-native-labels.yml",
    ".github/workflows/gamepulse-unattributed-native-source.yml",
    ".github/workflows/gamepulse-unified-native-search.yml",
    ".github/workflows/gamepulse-native-interactions-0095-blueprint-quarantine.yml",
    "tools/licensed_feed/official_pbp_onoff_28.py",
    ".github/workflows/gamepulse-28game-native-pbp-onoff.yml",
    ".github/workflows/rockets-wemby-opponent-ppp.yml",
    ".github/workflows/freeview-amen-732-private-visual-panels.yml",
    ".github/workflows/freeview-amen-732-private-audio-sync.yml",
    ".github/workflows/freeview-amen-732-private-native.yml",
    ".github/workflows/gamepulse-season-backlog.yml",
    ".github/workflows/gamepulse-20261024-final-fastlane.yml",
    ".github/workflows/gamepulse-rockets-spurs-fusion-merge.yml",
    ".github/workflows/gamepulse-rockets-spurs-original-qa.yml",
    "tools/licensed_feed/verify_gameplay_0009.py",
    "tools/licensed_feed/audit_sdk_metadata_0009.py",  # original private SHA-only schema inventory; no licensed values published
    ".github/workflows/public-nba-gravity-onegame.yml",
    ".github/workflows/nba-blueprint-priority-private-acquire.yml",
    "public_nba_gravity_rockets_game1_2026_27.json",
    "README.md",
    "PUBLIC_CONTENT_POLICY.md",
    "runner_policy.json",
    "bridge_consumer_heartbeat.json",
    "bridge_consumer_receipt.json",
    "bridge_execution_status.json",
    "bridge_result_summary.json",
    "tools/public_bridge_preflight.py",
    "tools/wait_for_consumer_receipt.py",
    "tools/public_content_guard.py",
    ".github/workflows/gamepulse-github-private-pilot.yml",
    "tools/licensed_feed/browser.js",
    "tools/licensed_feed/capture.mjs",
    "tools/licensed_feed/capture.test.mjs",
    "tools/licensed_feed/github_private_release.mjs",
    "tools/licensed_feed/github_private_release.test.mjs",
    "tools/licensed_feed/live_discovery.mjs",
    "tools/licensed_feed/live_discovery.test.mjs",
    "tools/licensed_feed/index.html",
    "tools/licensed_feed/package.json",
    "tools/licensed_feed/season_core.mjs",
    "tools/licensed_feed/season_core.test.mjs",
    "tools/licensed_feed/sdk_slot.mjs",
    "tools/licensed_feed/sdk_slot.test.mjs",
    "tools/licensed_feed/season_private_release.mjs",
    "tools/licensed_feed/verify_gameplay.py",
    ".github/workflows/gamepulse-gameplay-audit.yml",
    ".github/workflows/gamepulse-defender-spacing-qa.yml",
    ".github/workflows/gamepulse-rockets-private-clip-pilot.yml",
    ".github/workflows/nba-ring-only-private-pilot.yml",
    ".github/workflows/nba-jabari616-camera-qa.yml",
    ".github/workflows/nba-jabari616-frozen-ring-cpu-qa.yml",
    ".github/workflows/nba-jabari616-constant-ring-render.yml",
    ".github/workflows/nba-jabari616-constant-ring-v2.yml",
    ".github/workflows/nba-jabari616-ring-export-to-chat.yml",
    ".github/workflows/nba-jabari616-ball-handler-media.yml",
    ".github/workflows/nba-jabari616-cumulative-five-rings.yml",
    ".github/workflows/nba-jabari616-frozen-v31-quality.yml",
    ".github/workflows/nba-jabari616-frozen-v31-efficient.yml",
    ".github/workflows/nba-jabari616-frozen-v31-pulse-dense.yml",
    ".github/workflows/nba-jabari616-cumulative-play12.yml",
    ".github/workflows/nba-jabari616-five-ring-public-preview.yml",
    ".github/workflows/nba-jabari616-frozen-v31-public-video.yml",
    ".github/workflows/nba-jabari616-cumulative-receivers.yml",
    ".github/workflows/gamepulse-pnr-feasibility.yml",
    ".github/workflows/rockets-pnr-unified-review-qa.yml",
    ".github/workflows/rockets-pnr-video-source-diagnostic.yml",
    ".github/workflows/rockets-pnr-0075-gamepulse-review.yml",
    ".github/workflows/rockets-all-defensive-pnr-analysis.yml",
    ".github/workflows/gamepulse-pnr-ui-preflight.yml",
    ".github/workflows/gamepulse-github-season.yml",
    ".github/workflows/gamepulse-live-cle-phi-20261022.yml",
    ".github/workflows/gamepulse-cavs-native-seek-diagnostic.yml",
    ".github/workflows/gamepulse-live-all-games.yml",
    "tools/licensed_feed/live_capture_cycle.mjs",
    "tools/licensed_feed/live_capture_cycle.test.mjs",
    "tools/licensed_feed/live_discovery.mjs",
    "tools/licensed_feed/live_discovery.test.mjs",
    ".github/workflows/gamepulse-final-fastlane.yml",
    ".github/workflows/gamepulse-rockets-finalize-safeguard.yml",
    ".github/workflows/gamepulse-20261022-slate-backfill.yml",
    ".github/workflows/gamepulse-20261022-targeted-retry.yml",
    ".github/workflows/gamepulse-source-ready-final10.yml",
    ".github/workflows/gamepulse-part6-fast.yml",
    ".github/workflows/gamepulse-14game-world-source-qa.yml",
    ".github/workflows/gamepulse-private-search-index.yml",
    ".github/workflows/gamepulse-16game-private-search.yml",
    ".github/workflows/gamepulse-denver-sdk-recovery.yml",
    ".github/workflows/gamepulse-denver-official-pbp.yml",
    ".github/workflows/gamepulse-16game-coverage-qa.yml",
    ".github/workflows/gamepulse-denver-source-ready-retry.yml",
    ".github/workflows/gamepulse-private-blueprint-fusion.yml",
    ".github/workflows/gamepulse-2026-source-evidence.yml",
    ".github/workflows/gamepulse-official-onoff-qa.yml",
    ".github/workflows/gamepulse-formal-pbp-14game.yml",
    ".github/workflows/rockets-three-player-touch-probe.yml",
    ".github/workflows/rockets-native-touch-ppp.yml",
    ".github/workflows/gamepulse-native-interactions-14game.yml",
    ".github/workflows/gamepulse-interaction-query.yml",
    "tests/test_consumer_receipt_waiter.py",
    "tests/test_public_bridge_preflight.py",
    "tests/test_public_content_guard.py",
    ".github/workflows/run.yml",
    ".github/workflows/public-bridge-preflight-tests.yml",
    ".github/workflows/public-content-guard.yml",
    ".github/workflows/validate-public-bridge.yml",
    ".github/workflows/oneoff-sanitize-history.yml",
    ".github/workflows/post-sanitize-public-audit.yml",
    ".github/workflows/dispatch-oidc.yml",
}
# These already-public, manually inspected CPU-only workflow definitions are
# pinned to exact Git blobs. New or edited workflows must be re-reviewed;
# the pin does not authorize source datasets, binaries or public results.
REVIEWED_WORKFLOW_GIT_BLOB_SHA = {
    ".github/workflows/gamepulse-full107-pnr-private-20261104.yml": "142e85bb23d069a7b791f4258e68a5390a907cc8",  # reviewed pinned Full107 private-only screen detector; no licensed XYZ or per-event outputs public
    ".github/workflows/full107-first81-r13v2-0125-git-transport-20261104.yml": "b0cf74b51e93135a0b7ca736e289f14d275a398d",  # isolated original 0125 native replay via SHA git transport; private outputs only
    ".github/workflows/full107-first81-r17-reduce-only-private-20261104.yml": "c436551b7b9046fa01e31723e670c276c5691413",  # reviewed pinned private 9-shard R17 source-only analytical reduction; no public data
    ".github/workflows/full107-first81-r13v2-double-touchjoin-private-20261104.yml": "b0b514cec20dd55b85fbad7c885d62f1eb4855c9",  # reviewed original source 4-game first81 touch+double QA; private-only result
    ".github/workflows/full107-first81-doubleteam-r17-private-20261104.yml": "8e238e2107cc07980475bee27148a36666cc3b20",  # reviewed R17 81-game source-native paired CPU private-only, protected public logging
    ".github/workflows/full107-first81-doubleteam-audit-private-20261104.yml": "6714684763a643d138963e670bb4f8bf6a859f99",  # reviewed SHA-pinned private-only first81 manifest/reference validation; aggregate public counters
    ".github/workflows/nba-eason-0022600153-exact-action.yml": "5451e1d4731d4d7ad40186b36c30c64e89701896",  # reviewed immutable NBA public shot metadata and public replay locator only
    ".github/workflows/reed-0022600125-exact-action.yml": "1f039e96c534a7ea842e3053b6eb3b3d8fed041e",  # reviewed manual-only official public PBP, no signed media retrieval/persistence
    "reed_0022600125_official_action.json": "935a9ebcbe4177b8d642065e9392fc4f5952b069",  # immutable public NBA action metadata; hls_options empty, no signed URL
    ".github/workflows/gamepulse-pr776-oreb-control-stress.yml": "04e268929cca1ccdd2aa3f8428704000b3ab41f1",  # private original SDK read, aggregate control diagnostic only
    ".github/workflows/gamepulse-pr776-position-holdout-36.yml": "f9cec9925acde87472678c4695c6715068c73685",  # original private XYZ source, aggregate position error only
    ".github/workflows/gamepulse-pr776-new-eight-original-qa.yml": "3bd7f6f2a15a25048549a0fb74c362d8f650885f",  # original 13-part SDK, aggregate QA private only
    ".github/workflows/freeview-amen732-board-static-sources.yml": "70af49120ab48235cf4e4463f96b73026ce555c7",
    ".github/workflows/freeview-amen732-multipt-photo-refit.yml": "2e0dad12a628d892fdaddbdbc971e103f6119f48",  # original NBA private six-anchor + full 3PT photometric heldout, no public RGB
    ".github/workflows/gamepulse-pr776-sdk-metadata-0009.yml": "d1c768ec93f6f761b8245de8d21df58abf7257b0",  # reviewed private-only original SDK field-key QA; no values/XYZ in public
    ".github/workflows/gamepulse-igp-eight-native-raw-backfill.yml": "7a9790609ce84fb8c108c0bccb6b33954c886ae5",  # source chunks remain private
    ".github/workflows/gamepulse-igp-full-native-season-coverage.yml": "a2f69e668372cb88816c7ad2fa9cf0fcb9c14828",  # SHA-only private coverage and no public artifacts
    ".github/workflows/gamepulse-igp-full-native-batch.yml": "f9d1c67b8e6dfdd25be96e68aa95c5e8021a0615",  # private-only original SDK XYZ batch
    ".github/workflows/gamepulse-igp-private-release-browser-download-smoke.yml": "63cd4be67c16b15a078cb864741b0d6ad7fe96be",  # reviewed single part no-REST browser route probe, digest-gated no public artifacts
    ".github/workflows/gamepulse-igp-original-sdk-remaining-seven-recovery.yml": "d8ab67ad7eeb527c9ba56350918233d626ec41c6",  # private original 13-part SHA assets, native-only QA, never public licensed XYZ
    ".github/workflows/gamepulse-igp-all-native-rockets.yml": "984864df90f937a4f478c327d8fc5de4a2575f2a",  # source XYZ private only
    ".github/workflows/gamepulse-igp-sdk-native-full-game-0104.yml": "45f1b8ebbb00f506d2600debd81c8592bfc0f7cd",  # 13 original SHA-pinned private archives, aggregate-only logs and private QA
    ".github/workflows/gamepulse-igp-private-sdk-asset-direct-probe.yml": "afd02dfbf261b09217f8c25fcd787a53335e5665",  # exact SHA-pinned private one-part asset integrity-only probe; no artifact publication
    ".github/workflows/gamepulse-igp-oreb-clock-update-gates.yml": "4685c26a97bf41d305cb4df083780bfec25d96fc",  # private-only NBA event and clock queue, no public source data
    ".github/workflows/gamepulse-igp-original-xyz-continuity-clock-review.yml": "f7bcf3fecf79e15be5602a80725e5605e0f900db",  # no source/public XYZ; SHA-verified per-episode aggregated private QA
    ".github/workflows/gamepulse-pr776-possession-first-36-materialize.yml": "274e3640860a303d74da3fa79354bd54af6ea8ea",  # private-source-only 36-game materialization; no public artifacts or source records
    ".github/workflows/gamepulse-pr776-fresh-touch-successor-context.yml": "ebd5147288f91936b583a84dd0f17c82dfcfd01b",  # reviewed private-only 93 candidate NBA context CPU with no public artifacts
    ".github/workflows/freeview-amen732-right-above-rim-metric.yml": "75667982d792310e56dca5f31d70492563a2e5cf",  # original NBA gamepulse world stable court KRT trial, private heldout and UHD QA
    ".github/workflows/freeview-amen732-static-right-above-rim.yml": "1b1cb13cede4778be8f697b8211db425dbd4ad58",  # original static right-above-rim private NBA court-source geometry and 4K QA
    ".github/workflows/freeview-amen732-high-tight-third-view.yml": "82d5b42a0ec14f47214c1257fecb44c40eab802e",  # exact SHA original High Tight third view, private-only 4K contact sheet
    ".github/workflows/freeview-amen732-left-long-research-pts.yml": "c79abf52f144b479452b8bc6fddd0cc55de32c00",  # Git-only private original NBA source; provisional PTS explicitly blocked for metric claims
    ".github/workflows/freeview-amen732-two-slash-extended-native.yml": "858e856f1b1a00718f1a4187c3860a1326c4cd42",  # source-native left/right Slash NBA clips, private-only 30fps contours
    ".github/workflows/gamepulse-pr776-original-xyz-search-audit.yml": "c3f846ddaacff6dbc4066e6dbf9a16d05bb4fff9",  # private authenticated Git; ephemeral source-only audit; aggregate logs
    ".github/workflows/gamepulse-pr776-event-episode-crosswalk-test.yml": "2e2c139ff6174c9927764513c423de89a31e3aa0",  # reviewed: private CPU-only exact-action tests, aggregate logs, no artifacts
    ".github/workflows/freeview-amen732-sam2-world-camera-holdout.yml": "649305ab47e78d343883e87e046bd5b2600559d7",  # private SAM2 native ball centroids and original world XYZ; aggregate-only public logs
    ".github/workflows/freeview-amen732-sam21-23-source-frames.yml": "242444981ff930b70f6a29e7bcc931a2efc42121",  # pinned Meta CPU, original 24 source NBA stills, private-only masks
    ".github/workflows/freeview-amen732-43xyz-23pixel-holdout.yml": "7fb576f1e6cc7803f4aad2d746eedb3ff3e570eb",  # original NBA SDK/X/Y/Z CPU holdouts; private-only coordinates and QA
    ".github/workflows/gamepulse-rockets-event-xyz.yml": "0814eefa14b62583095919d77b2368242d90cccb",  # reviewed: SHA-verified SDK, private XYZ output and aggregate public QA
    ".github/workflows/freeview-amen732-q4-sdk-proof.yml": "ff86bee5bc3eb2b4b368f47d07f8aa7d4d187e9e",  # re-reviewed: SHA-verified private Q4 original, byte-exact idempotent private fixture only, no public export
    ".github/workflows/gamepulse-pr776-bulk-four-game-xyz.yml": "86bb20b96d0210becbc54c69c5b038b3adbb8074",
    ".github/workflows/gamepulse-pr776-bulk-0009-original-xyz.yml": "6306d60e989e0537c6469d49ab18bbed576d0846",
    ".github/workflows/pr776-shared-token-rate-diagnostic.yml": "d3c639f2f0aa6a3195e14a9aecbc2ce767bb646f",  # aggregate only; shared credential status, no SDK asset export
    ".github/workflows/gamepulse-pr776-native-event-windows.yml": "4b05a4ef1f1928aced957f16ae4d577442770d58",  # reviewed private NBA/native guarded research windows no raw SDK coordinates
    ".github/workflows/gamepulse-pr776-private-event-xyz.yml": "b6d5fdbda5f2bd7c7aee13034119204027593b24",  # private-only SHA-verified SDK event subset; no coordinates in public logs
    ".github/workflows/gamepulse-pr776-event-first-36.yml": "9b011124c37e807ded708eb9ea720e2efb8cbe58",  # reviewed: private aggregate lookup and held-out position QA
    ".github/workflows/gamepulse-pr776-clock-shadow-study.yml": "844ff228aecad1a2537d4d986329e7b498d015bc",  # reviewed: private SHA-pinned clock QA, no raw source export or physical certification
    ".github/workflows/gamepulse-pr776-release-direct-pilot.yml": "5cd5cc5b299537a12f13a549e8f978b168a88b2a",  # reviewed private release download, no public artifact or coordinates
    ".github/workflows/gamepulse-video-free-clock-season.yml": "50f57ae8e3e6db0523dd25246110664b846441da",  # reviewed: original SHA-checked NBA SDK made-hoop QA only, private writes
    ".github/workflows/gamepulse-pr776-nba-36-episodes.yml": "edf6cce97c6db0d4b3775d172116813a6eb73aae",  # reviewed: private sparse source, full 36 SHA episode replay, old 28 preserved
    ".github/workflows/gamepulse-pr776-official-36game-expansion.yml": "a87ef5db6b672f78322fe49f4f9b46923cc17780",  # reviewed: private sparse git only; NBA official PBP/provider, 8-game addition, no public source files
    ".github/workflows/gamepulse-pr776-episode-season-search.yml": "e99e5e228ba930b89417cc80b7fd7a67a45a883b",  # reviewed: private aggregate-only 28-game episode QA index, no source XYZ publication
    ".github/workflows/gamepulse-pr776-official-native-xyz-bridge.yml": "bfff7805d3833a6d76beca6573a8e1a33aecc88a",  # reviewed: private 13-part SDK, source-independent tests, private-only aggregate XYZ QA
    ".github/workflows/gamepulse-official-lineup-clock-28.yml": "5e3ff52f3cf5825f4457c8dcea9ba72f828d7c28",  # reviewed: 28-game official PBP/provider CPU, private-only identities and aggregate public QA
    ".github/workflows/gamepulse-rockets-official-five-recovery.yml": "8f01ef993d7285ffce8c03e2ff2d1dc349f0b20e",  # reviewed: official NBA provider, private-only result; aggregate logs
    ".github/workflows/clip-lab-sengun-hawks-hls.yml": "cc7f972f9d51cc7aafe10fa71f0b395638bbed74",  # reviewed: NBA public event probe, metadata-only logs, no artifacts
    ".github/workflows/clip-lab-frozen-ring-sprites.yml": "a002f86a91280330248438f837bb2d5e7c51d99c",  # inspected: only generated RGBA ring sprites and metadata uploaded
    ".github/workflows/clip-lab-rockets-219-hls.yml": "16d9d45f0d718271049b894adbdf8375b9d22b5d",
    ".github/workflows/clip-lab-rockets-new-double-346-hls.yml": "330309713345d92819ebf61f46ca39fc7d7df969",
    ".github/workflows/clip-lab-rockets-new-double-353-hls.yml": "0fe06a115dd1f2c18c74a1be28753f1d63d41a44",
    ".github/workflows/clip-lab-rockets-new-double-616-hls.yml": "6b3185d4281a537492472914901102668bd409de",
    ".github/workflows/durant-context-inspection.yml": "90af2d117e4206b44861283e95e0c9440eca90d1",
    ".github/workflows/gamepulse-rockets-durant-double-review-v4.yml": "f396fc7957b5a49f8b9abb38bbb309a17b1c1c1a",
    ".github/workflows/gamepulse-rockets-event616-double-fn.yml": "8490170f6437241f4098bf6f0bd853ed91726149",
    ".github/workflows/gamepulse-rockets-sengun-double-4ft.yml": "2fd90ab0271963a3cfb9bf64336d50bbb0c78ab7",
    ".github/workflows/gamepulse-rockets-sengun-double-4ft-v2.yml": "0b870d0e02b71eebcee3bc3a890fe24530dfee68",
    ".github/workflows/gamepulse-rockets-sengun-double-relaxed-v3.yml": "0a6caf4914853cb8487468c092a01f7c7bd0279c",
    ".github/workflows/gamepulse-rockets-sengun-hub-qa.yml": "e9a8a41ab0d8b6ecf390d2fb847a8d2351765dbe",
    ".github/workflows/nba-jabari616-ball-handler-media.yml": "779830fa72713804709cc6455a91c702586c784b",
    ".github/workflows/nba-jabari616-pulse-frozen-ring-render.yml": "e0e9621b82a6da6f31bf27cbeb71232403fd346b",
    ".github/workflows/gamepulse-wemby-advanced-boxscore-0022600009.yml": "0aab6eb3a993d9d6a88776bad4a233029748c7ef",
    ".github/workflows/nba-jabari616-ring-export-to-chat.yml": "f63f723f34e03b12723389b1e84b3eb6de5b4e6e",
    ".github/workflows/rockets-durant-double-team-clip-verification.yml": "2d9573e710d1ad19e7ee68a202f35a8775cb4503",
    ".github/workflows/rockets-durant-reviewed-halfcourt-v5.yml": "bdb6e1d1062dff439c19ca85c8191c71a9aaecc8",
    ".github/workflows/rockets-remaining-sengun-double-clips.yml": "8f2a1d85f88845732f1139740eede73604cbde2c",
}

# Two reviewed, immutable handoff workflows may upload only their audited
# artifacts. In particular, the encrypted handoff's recipient certificate must
# also remain byte-for-byte pinned: changing the recipient would expose the
# private source bundle to an unintended decryptor.
REVIEWED_ARTIFACT_HANDOFF_GIT_BLOB_SHA = {
    ".github/workflows/clip-lab-artifact-handoff-smoke.yml": "c82cd5194d384e32acd1bf0cb42a0064e5703af7",
    ".github/workflows/clip-lab-encrypted-event86-handoff.yml": "4fb87ada769b0422c24afae0a60470c0d04bae3b",
}
REVIEWED_HANDOFF_CERT_GIT_BLOB_SHA = {
    "tools/clip_lab_public_handoff_cert.pem": "b3e84c69c35e061580dd3a4e6201c07f4adbdc19",
}

REVIEWED_PUBLIC_NBA_ACTION_METADATA = {
    ".github/workflows/reed-0022600125-exact-action.yml",
    "reed_0022600125_official_action.json",
}
REVIEWED_MEDIA_SOURCE_WORKFLOWS = {
    ".github/workflows/nba-eason-0022600153-replay-access-probe.yml",  # inspected NBA public replay origin HTTP-only, no private media
    ".github/workflows/nba-eason-0022600153-exact-action.yml",  # pinned immutable official NBA public replay-link origin only
    "tools/amen732_official_sixvideo_acquire.py",  # audited official NBA source page only, no signed URLs stored
    "tools/amen732_official_sixvideo_acquire.py",  # vetted native official HLS acquisition; never persists URLs or footage publicly
    ".github/workflows/freeview-amen732-direct-sixvideo-render.yml",  # public NBA stream source only; no native media artifacts
    "tools/amen732_freeview_sixvideo_public_source.py",  # only the public event page origin, no signed stream values committed
    ".github/workflows/freeview-amen732-official-sixstream-source-probe.yml",  # Official public NBA six-stream probe; no private release or artifacts
    ".github/workflows/clip-lab-sengun-hawks-hls.yml",  # pinned, public clips origin only; no raw URL output or artifacts
    ".github/workflows/clip-lab-rockets-219-hls.yml",
    ".github/workflows/clip-lab-rockets-new-double-346-hls.yml",
    ".github/workflows/clip-lab-rockets-new-double-353-hls.yml",
    ".github/workflows/clip-lab-rockets-new-double-616-hls.yml",
    ".github/workflows/rockets-durant-double-team-clip-verification.yml",
    ".github/workflows/rockets-remaining-sengun-double-clips.yml",
}
REVIEWED_PUBLIC_MP4_EXPORT_WORKFLOWS = {
    ".github/workflows/freeview-amen732-direct-sixvideo-render.yml",  # public NBA stream source only; no native media artifacts
    ".github/workflows/clip-lab-event80-direct-native-frozen.yml",  # one final QA-approved annotated MP4, never private source/tracking
    ".github/workflows/clip-lab-rockets-event80-frozen-render.yml",  # ONLY QA-approved ringed MP4 artifact
    ".github/workflows/clip-lab-event80-delivery-smoke.yml",  # harmless test fixture upload
    ".github/workflows/nba-jabari616-ball-handler-media.yml",
    ".github/workflows/nba-jabari616-ring-export-to-chat.yml",
    ".github/workflows/nba-jabari616-cumulative-receivers.yml",
}
# Reviewed immutable sprite export produces only generated RGBA PNG atlases and metadata;
# no source positions, tracking frames, or raw private SDK observations are uploaded.
REVIEWED_PUBLIC_SPRITE_EXPORT_WORKFLOWS = {
    ".github/workflows/clip-lab-frozen-ring-sprites.yml",
}
ALLOWED_PREFIXES = {"bridge_outbox/"}
FORBIDDEN_PREFIXES = {
    "experiments/",
    "experiment_results/",
    "prepared/",
    "models/",
    "checkpoints/",
    "fixtures/",
    "datasets/",
}
FORBIDDEN_EXT = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".pt", ".pth", ".onnx", ".engine", ".safetensors",
    ".csv", ".parquet", ".npz", ".npy", ".pkl", ".pickle",
}
TEXT_PATTERNS = [
    ("GCS_URI", re.compile(r"gs://", re.I)),
    ("SERVICE_ACCOUNT", re.compile(r"iam\.gserviceaccount\.com", re.I)),
    ("GCP_PROJECT_STYLE_ID", re.compile(r"\bproject-[a-z0-9][a-z0-9-]{4,}\b", re.I)),
    ("ACTIONS_ARTIFACT_UPLOAD", re.compile(r"actions/upload-artifact@", re.I)),
    ("DIRECT_PRIVATE_REPO_CHECKOUT", re.compile(r"repository:\s*[^\n]+/104\b", re.I)),
    ("MEDIA_SOURCE_URL", re.compile(r"(youtube\.com/watch|clips\.nba\.com)", re.I)),
]
REQUEST_RE = re.compile(r"^req-[0-9a-f]{32}$")

def tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "-z"])
    return [x.decode() for x in out.split(b"\0") if x]

def violation(code: str, path: str) -> tuple[str, str]:
    return (code, path)

def scan(paths: list[str]) -> list[tuple[str, str]]:
    bad: list[tuple[str, str]] = []
    for rel in paths:
        p = Path(rel)
        if any(rel.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            bad.append(violation("FORBIDDEN_PATH_CLASS", rel))
            continue
        if p.suffix.lower() in FORBIDDEN_EXT:
            bad.append(violation("FORBIDDEN_FILE_TYPE", rel))
            continue
        if rel not in ALLOWED_STATIC and rel not in REVIEWED_WORKFLOW_GIT_BLOB_SHA and not any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            bad.append(violation("NOT_ALLOWLISTED", rel))
            continue
        if not p.is_file():
            continue
        pinned_sha = (
            REVIEWED_WORKFLOW_GIT_BLOB_SHA.get(rel)
            or REVIEWED_ARTIFACT_HANDOFF_GIT_BLOB_SHA.get(rel)
            or REVIEWED_HANDOFF_CERT_GIT_BLOB_SHA.get(rel)
        )
        if pinned_sha:
            current = subprocess.check_output(["git", "hash-object", rel], text=True).strip()
            if current != pinned_sha:
                bad.append(violation("REVIEWED_WORKFLOW_OR_CERT_CHANGED", rel))
                continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            bad.append(violation("NON_TEXT_FILE", rel))
            continue
        # The guard contains literal detection patterns by design; do not
        # flag its own source for defining those patterns.
        if rel != "tools/public_content_guard.py":
            for code, rx in TEXT_PATTERNS:
                # User-authorised publication of ONE rendered NBA clip, never
                # raw tracking or canonical private database records.
                if (code == "ACTIONS_ARTIFACT_UPLOAD" and
                    (rel in REVIEWED_PUBLIC_MP4_EXPORT_WORKFLOWS
                     or rel in REVIEWED_PUBLIC_SPRITE_EXPORT_WORKFLOWS
                     or rel in REVIEWED_ARTIFACT_HANDOFF_GIT_BLOB_SHA)):
                    continue
                # Existing exact-blob NBA clip locator workflows contain the
                # public clips.nba.com origin, never signed media URLs.
                if (code == "MEDIA_SOURCE_URL" and
                    (rel in REVIEWED_MEDIA_SOURCE_WORKFLOWS or
                     (rel in REVIEWED_PUBLIC_NBA_ACTION_METADATA and pinned_sha)) and
                    all(m.group(0).lower() == "clips.nba.com"
                        for m in rx.finditer(text))):
                    continue
                if rx.search(text):
                    bad.append(violation(code, rel))
    rid = Path("REQUEST_ID")
    if rid.exists():
        value = rid.read_text().strip()
        if value and not REQUEST_RE.fullmatch(value):
            bad.append(violation("SEMANTIC_OR_INVALID_REQUEST_ID", "REQUEST_ID"))
    return sorted(set(bad))

def main() -> int:
    bad = scan(tracked_files())
    if bad:
        for code, path in bad:
            print(f"PUBLIC_CONTENT_GUARD_FAIL code={code} path={path}")
        return 3
    print("PUBLIC_CONTENT_GUARD_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
