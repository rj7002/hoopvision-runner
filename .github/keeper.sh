#!/usr/bin/env bash
# Starts the live capture workflow only around game times (see keeper.yml for why a keeper exists at all).
#   KEEPER_PLAN_ONLY=1         print what it sees and would do right now, then stop
#   KEEPER_SCHEDULE_FILE=path  read the schedule JSON from a file instead of cdn.nba.com (testing)
#   KEEPER_NOW=epoch           pretend it is this time (testing)
set -o pipefail

CAPTURE=gamepulse-live-evergreen-original-xyz.yml
SCHEDULE_URL=https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json
LEAD=900            # start dispatching this long before a tip-off (the capture workflow picks a game up 8 min before it)
NEAR_AFTER=600      # ... and keep going often until this long after it
NEAR_GAP=120        # seconds between dispatches around a tip-off
LIVE_WINDOW=21600   # the capture workflow keeps a game eligible for 6 hours after its scheduled tip
LIVE_GAP=1200       # seconds between dispatches while a game is on (restarts a runner that died)
FALLBACK_GAP=300    # schedule unavailable: dispatch every 5 minutes

now() { echo "${KEEPER_NOW:-$(date +%s)}"; }
log() { echo "[$(date -u +%H:%M:%S)Z] $*"; }

tips=()
load_schedule() {
  local t raw out tip; t=$(now)
  if [ -n "${KEEPER_SCHEDULE_FILE:-}" ]; then
    raw=$(cat "$KEEPER_SCHEDULE_FILE") || return 1
  else
    raw=$(curl -fsS --max-time 25 -H 'User-Agent: Mozilla/5.0' -H 'Referer: https://www.nba.com/' "$SCHEDULE_URL") || return 1
  fi
  # tip-off times (epoch seconds) from 7 hours ago to 36 hours ahead
  out=$(jq -r --argjson now "$t" '
      if (.leagueSchedule.gameDates | length) < 1 then error("no dates") else . end
      | .leagueSchedule.gameDates[].games[]
      | select(.gameId | test("^00[1-5][0-9]{7}$"))
      | (.gameDateTimeUTC | fromdateiso8601) as $tip
      | select($tip > $now - 25200 and $tip < $now + 129600)
      | $tip' <<<"$raw") || return 1
  tips=()
  while IFS= read -r tip; do [ -n "$tip" ] && tips+=("$tip"); done <<<"$out"
  return 0
}

gap_now() {  # seconds between dispatches right now; 0 = no game near, do nothing
  local t tip d near=0 live=0; t=$(now)
  for tip in "${tips[@]}"; do
    d=$((t - tip))
    if [ "$d" -ge $((-LEAD)) ] && [ "$d" -le "$NEAR_AFTER" ]; then near=1; fi
    if [ "$d" -ge $((-LEAD)) ] && [ "$d" -le "$LIVE_WINDOW" ]; then live=1; fi
  done
  if [ $near = 1 ]; then echo "$NEAR_GAP"; elif [ $live = 1 ]; then echo "$LIVE_GAP"; else echo 0; fi
}

if [ -n "${KEEPER_PLAN_ONLY:-}" ]; then
  if load_schedule; then
    echo "schedule ok: ${#tips[@]} games from 7 h ago to 36 h ahead"
    for tip in "${tips[@]}"; do echo "  tip $(date -u -d "@$tip" '+%a %H:%M UTC' 2>/dev/null || date -u -r "$tip" '+%a %H:%M UTC')"; done | head -24
    echo "dispatch gap right now: $(gap_now)s (0 = idle)"
  else
    echo "schedule NOT available: would dispatch every ${FALLBACK_GAP}s"
  fi
  exit 0
fi

end=$((SECONDS + 20700))      # 5 h 45 min
handover=$((SECONDS + 20100)) # 5 h 35 min: queue the next keeper
queued=0; last=-100000; ok=0; loaded=-100000
while [ "$SECONDS" -lt "$end" ]; do
  if [ $((SECONDS - loaded)) -ge 1800 ] || { [ $ok = 0 ] && [ $((SECONDS - loaded)) -ge 300 ]; }; then
    if load_schedule; then ok=1; log "schedule loaded: ${#tips[@]} games nearby"
    else ok=0; log "schedule unavailable; dispatching every ${FALLBACK_GAP}s until it is"; fi
    loaded=$SECONDS
  fi
  if [ $ok = 1 ]; then gap=$(gap_now); else gap=$FALLBACK_GAP; fi
  if [ "$gap" -gt 0 ] && [ $((SECONDS - last)) -ge "$gap" ]; then
    if gh workflow run "$CAPTURE" --ref main; then log "dispatched capture (gap ${gap}s)"; else log "dispatch failed"; fi
    last=$SECONDS
  fi
  if [ "$queued" = 0 ] && [ "$SECONDS" -ge "$handover" ]; then
    gh workflow run keeper.yml --ref main && queued=1 && log "queued the next keeper"
  fi
  sleep 30
done
