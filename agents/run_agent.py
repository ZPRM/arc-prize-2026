"""
ARC Prize 2026 - Agent Runner
Called by GitHub Actions workflow: .github/workflows/run_agent.yml
"""

import os
import json
import random
import requests
from datetime import datetime, timezone
from pathlib import Path

import arc_agi
from arcengine import GameAction, GameState

# Config
ARC_API_KEY    = os.getenv("ARC_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID", "322d1613bdbd810481b6d403b8b8f2ba")
GAME           = os.getenv("GAME", "all")
MAX_ACTIONS    = int(os.getenv("MAX_ACTIONS", "500"))

ALL_GAMES    = ["ls20", "ft09", "vc33"]
GAMES_TO_RUN = ALL_GAMES if GAME == "all" else [GAME]

Path("results").mkdir(exist_ok=True)

def run_agent(game_id: str, max_actions: int) -> dict:
    print(f"\n{'='*50}")
    print(f"Running agent on: {game_id}")
    print(f"{'='*50}")

    arc = arc_agi.Arcade()
    env = arc.make(game_id)

    if env is None:
        return {"game": game_id, "error": "environment creation failed"}

    actions_taken = 0
    wins = 0
    levels_completed = 0

    for step in range(max_actions):
        actions = env.action_space
        action = random.choice(actions)
        action_data = {}

        if action.is_complex():
            action_data = {
                "x": random.randint(0, 63),
                "y": random.randint(0, 63),
            }

        obs = env.step(action, data=action_data)
        actions_taken += 1

        if obs and obs.state == GameState.WIN:
            wins += 1
            levels_completed += 1
            print(f"  WIN at step {step}! Total wins: {wins}")
            env.reset()

        if step % 100 == 0 and step > 0:
            print(f"  Step {step}/{max_actions} | Wins: {wins}")

    scorecard = arc.get_scorecard()
    print(f"\nFinal scorecard for {game_id}: {scorecard}")

    return {
        "game": game_id,
        "actions_taken": actions_taken,
        "wins": wins,
        "levels_completed": levels_completed,
        "scorecard": str(scorecard),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def push_to_notion(results):
    if not NOTION_API_KEY:
        print("No NOTION_API_KEY — skipping Notion push")
        return

    url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    run_number = os.getenv("GITHUB_RUN_NUMBER", "manual")
    timestamp  = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")

    lines = [f"GitHub Actions Run #{run_number} — {timestamp}", ""]
    for r in results:
        if "error" in r:
            lines.append(f"{r['game']}: ERROR — {r['error']}")
        else:
            lines.append(
                f"{r['game']}: {r['actions_taken']} actions | "
                f"{r['levels_completed']} levels | {r['scorecard']}"
            )

    blocks = [
        {"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {
                "content": f"Agent Run #{run_number} — {timestamp}"
            }}]
        }},
        {"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": "\n".join(lines)}}]
        }},
        {"object": "block", "type": "divider", "divider": {}},
    ]

    r = requests.patch(url, headers=headers, json={"children": blocks})
    print(f"Notion push: {'OK' if r.status_code == 200 else r.status_code}")

if __name__ == "__main__":
    print(f"ARC Prize 2026 — Agent Runner")
    print(f"Games: {GAMES_TO_RUN} | Max actions: {MAX_ACTIONS}")

    all_results = []
    for game in GAMES_TO_RUN:
        result = run_agent(game, MAX_ACTIONS)
        all_results.append(result)
        out_path = f"results/{game}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

    combined = f"results/run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    with open(combined, "w") as f:
        json.dump(all_results, f, indent=2)

    push_to_notion(all_results)
    print("\nDone!")
