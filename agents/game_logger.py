"""
ARC Prize 2026 - Game State Logger
===================================
Automatically captures every state transition for all 3 games.
No screenshots needed. No manual play needed.
Runs at 2000 FPS locally.

Usage in Colab:
    from agents.game_logger import GameLogger
    logger = GameLogger()
    logger.inspect_raw_state('ls20')   # STEP 1: see what data API gives us
    logger.explore_game('ls20')        # STEP 2: auto-explore and log
    logger.save_all()                  # STEP 3: save findings
"""

import os, json, random, time
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
import arc_agi
from arcengine import GameAction, GameState

Path("game_logs").mkdir(exist_ok=True)
Path("game_analysis").mkdir(exist_ok=True)


class GameLogger:
    """
    Automatically explores ARC-AGI-3 games and logs every state transition.
    Replaces manual screenshot capture entirely.
    """

    def __init__(self):
        self.logs = defaultdict(list)
        self.state_changes = defaultdict(list)
        self.action_effects = defaultdict(lambda: defaultdict(int))

    # ── STEP 1: Raw state inspection ──────────────────────────────────────

    def inspect_raw_state(self, game_id: str):
        """
        Print the raw observation structure.
        Run this FIRST to understand exactly what data the API gives us.
        This is the most important function -- tells us what state variables exist.
        """
        print(f"\n{'='*60}")
        print(f"RAW STATE INSPECTION: {game_id}")
        print(f"{'='*60}")

        arc = arc_agi.Arcade()
        env = arc.make(game_id)
        if env is None:
            print("Failed to create environment")
            return

        obs = env.observe()

        print(f"\n--- Type of observation ---")
        print(type(obs))

        print(f"\n--- Raw observation (initial state) ---")
        print(obs)

        print(f"\n--- Available attributes ---")
        attrs = [x for x in dir(obs) if not x.startswith('_')]
        print(attrs)
        for attr in attrs:
            try:
                val = getattr(obs, attr)
                if not callable(val):
                    print(f"  obs.{attr} = {val}")
            except:
                pass

        print(f"\n--- Action space ---")
        for action in env.action_space:
            print(f"  {action} | is_complex: {action.is_complex()}")

        print(f"\n--- Testing each action (which ones change state?) ---")
        for action in env.action_space:
            obs_before = str(env.observe())
            d = {"x": 32, "y": 32} if action.is_complex() else {}
            env.step(action, data=d)
            obs_after = str(env.observe())
            changed = obs_before != obs_after
            print(f"  {str(action):35s} -> {'CHANGED ✅' if changed else 'no change ❌'}")

        return obs

    # ── STEP 2: Full exploration ───────────────────────────────────────────

    def explore_game(self, game_id: str, n_episodes: int = 5, max_actions: int = 200):
        """Auto-explore a game, logging every state transition."""
        print(f"\n{'='*60}")
        print(f"EXPLORING: {game_id} | {n_episodes} episodes x {max_actions} actions")
        print(f"{'='*60}")

        for ep in range(n_episodes):
            print(f"\n--- Episode {ep+1}/{n_episodes} ---")
            arc = arc_agi.Arcade()
            env = arc.make(game_id)
            if env is None:
                continue

            wins = 0
            for step in range(max_actions):
                obs_b = str(env.observe())
                action = random.choice(env.action_space)
                d = {"x": random.randint(0, 63), "y": random.randint(0, 63)} if action.is_complex() else {}
                result = env.step(action, data=d)
                obs_a = str(env.observe())
                changed = obs_b != obs_a

                t = {
                    "episode": ep, "step": step,
                    "action": str(action), "action_data": d,
                    "state_before": obs_b[:300],
                    "state_after": obs_a[:300],
                    "state_changed": changed,
                    "game_state": str(result.state) if result else "unknown",
                }
                self.logs[game_id].append(t)

                aname = str(action).split(".")[-1]
                self.action_effects[game_id][aname + ("_c" if changed else "_u")] += 1
                if changed:
                    self.state_changes[game_id].append(t)

                if result and result.state == GameState.WIN:
                    wins += 1
                    print(f"  WIN at step {step}!")
                    env.reset()

            print(f"  Done: {len(self.logs[game_id])} transitions | "
                  f"{wins} wins | {len(self.state_changes[game_id])} state changes")

        self._print_analysis(game_id)

    def _print_analysis(self, game_id: str):
        total = len(self.logs[game_id])
        changed = len(self.state_changes[game_id])
        if total == 0:
            return

        print(f"\n📊 {game_id} Analysis:")
        print(f"  State change rate: {changed}/{total} = {changed/total*100:.1f}%")
        print(f"  (Low % = most actions do nothing = why random agents fail!)\n")

        effects = self.action_effects[game_id]
        names = set(k.replace("_c", "").replace("_u", "") for k in effects)
        print(f"  Which actions cause state changes:")
        for a in sorted(names):
            c = effects.get(a + "_c", 0)
            u = effects.get(a + "_u", 0)
            t = c + u
            pct = c / t * 100 if t > 0 else 0
            bar = "█" * int(pct / 5)
            print(f"    {a:25s}: {pct:5.1f}% {bar} ({c}/{t})")

    # ── STEP 3: Save everything ────────────────────────────────────────────

    def save_all(self):
        """Save all logs and analysis to files."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

        for gid in self.logs:
            path = f"game_logs/{gid}_{ts}.json"
            data = {
                "game_id": gid,
                "timestamp": ts,
                "total_transitions": len(self.logs[gid]),
                "state_changes": len(self.state_changes[gid]),
                "action_effects": dict(self.action_effects[gid]),
                "sample_transitions": self.logs[gid][:500],
                "sample_state_changes": self.state_changes[gid][:100],
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Saved: {path}")

        # Summary
        summary = f"game_analysis/summary_{ts}.txt"
        with open(summary, "w") as f:
            f.write(f"ARC Prize 2026 - Game State Analysis\nGenerated: {ts}\n\n")
            for gid in self.logs:
                total = len(self.logs[gid])
                changed = len(self.state_changes[gid])
                f.write(f"{'='*40}\n{gid}\n{'='*40}\n")
                f.write(f"Transitions: {total}\n")
                f.write(f"State changes: {changed} ({changed/total*100:.1f}%)\n\n")
                effects = self.action_effects[gid]
                names = set(k.replace("_c","").replace("_u","") for k in effects)
                for a in sorted(names):
                    c = effects.get(a+"_c", 0)
                    u = effects.get(a+"_u", 0)
                    t = c + u
                    pct = c/t*100 if t > 0 else 0
                    f.write(f"  {a}: {pct:.1f}% effective ({c}/{t})\n")
                f.write("\n")
        print(f"✅ Summary: {summary}")


# ── Colab cells (copy-paste these) ────────────────────────────────────────
#
# Cell 1 — setup
# !pip install arc-agi -q
# import os; os.environ['ARC_API_KEY'] = 'your-key-here'
# import sys; sys.path.append('/content/arc-prize-2026')
# from agents.game_logger import GameLogger
# logger = GameLogger()
#
# Cell 2 — inspect raw state (MOST IMPORTANT, run first!)
# for game in ['ls20', 'ft09', 'vc33']:
#     logger.inspect_raw_state(game)
#
# Cell 3 — full exploration
# for game in ['ls20', 'ft09', 'vc33']:
#     logger.explore_game(game, n_episodes=3, max_actions=200)
# logger.save_all()

if __name__ == "__main__":
    logger = GameLogger()
    print("Step 1: Raw state inspection")
    for game in ["ls20", "ft09", "vc33"]:
        logger.inspect_raw_state(game)
    print("\nStep 2: Exploration")
    for game in ["ls20", "ft09", "vc33"]:
        logger.explore_game(game, n_episodes=3, max_actions=100)
    print("\nStep 3: Save")
    logger.save_all()
