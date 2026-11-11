# NBA Game Pulse Live Capture

This is an attributed fork of [timeedmonds-maker/hoopvision-runner](https://github.com/timeedmonds-maker/hoopvision-runner). It is trimmed to the NBA Game Pulse live tracking collector and its tests. The upstream workflow, SDK integration, and capture logic remain credited to the upstream author; this fork only changes the private storage destination configuration.

## What it does

- Checks the official NBA schedule every five minutes.
- Starts one CPU-only GitHub-hosted job per active or imminent game.
- Captures only authentic SDK-observed player/ball tracking responses; it does not invent or interpolate missing positions.
- Checks for the official final-game status and makes a bounded post-final capture attempt.
- Stores source payloads and checkpoints only in the configured private GitHub repository, with SHA-256 readback verification. The public runner does not upload data as public Actions artifacts.

GitHub-hosted scheduled workflows can be delayed, so exact tip-off timing is not guaranteed. Capture completeness depends on the NBA feed and the authorized SDK session remaining available.

## Configure before enabling Actions

Actions is currently disabled for this fork. First create these settings in the fork's **Settings → Secrets and variables → Actions**:

- Secret `GAMEPULSE_PRIVATE_DATA_REPO`: your private repository slug, in `owner/name` form.
- Secret `GAMEPULSE_PRIVATE_RELEASE_TOKEN`: a fine-grained token or GitHub App token scoped only to that private repository. Grant the minimum required repository contents and release permissions.
- Variable `GAMEPULSE_PRIVATE_DATA_BRANCH`: `gamepulse-original-captures`.

The private destination branch is already created in the configured data repository. Never put tokens or private tracking data in this public repository, workflow YAML, logs, or public artifacts.

Only `.github/workflows/gamepulse-live-evergreen-original-xyz.yml` is intended to run for live collection. Keep unrelated workflows disabled if they are reintroduced. To avoid a burst of old scheduled jobs, verify the enabled workflow list before turning Actions on.

## Upstream

- Source repository: [timeedmonds-maker/hoopvision-runner](https://github.com/timeedmonds-maker/hoopvision-runner)
- The GitHub fork relationship is retained. The upstream author can see that this is a fork; this repository does not attempt to conceal its origin.
