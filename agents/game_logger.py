"""
ARC Prize 2026 - Game State Logger
===================================
Automatically captures every state transition for all 3 games.
No screenshots needed. No manual play needed.

Correct API (from docs.arcprize.org/toolkit/environment_wrapper):
    env.observation_space  -> FrameDataRaw (property, not method!)
    env.action_space       -> list[GameAction]
    env.info               -> EnvironmentInfo
    env.step(action)       -> FrameDataRaw
    env.reset()            -> FrameDataRaw

Usage in Colab:
    from agents.game_logger import GameLogger
    logger = GameLogger()
    logger.inspect_raw_state('ls20')
    logger.explore_game('ls20')
    logger.save_all()
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

    def __init__(self):
        self.logs = defaultdict(list)
        self.state_changes = defaultdict(list)
        self.action_effects = defaultdict(lambda: defaultdict(int))

    # ── STEP 1: Raw state inspection ──────────────────────────────────────

    def inspect_raw_state(self, game_id: str):
        """
        Print the raw observation structure.
        Run this FIRST to understand exactly what data the API gives us.
        API: env.observation_space (property) not env.observe() (method)
        """
        print(f"\n{'='*60}")
        print(f"RAW STATE INSPECTION: {game_id}")
        print(f"{'='*60}")

        arc = arc_agi.Arcade()
        env = arc.make(game_id)
        if env is None:
            print("Failed to create environment")
            return

        # ── env.info ──────────────────────────────────────────────────────
        print(f"\n--- env.info ---")
        try:
            info = env.info
            print(f"  Type: {type(info)}")
            print(f"  game_id: {info.game_id}")
            print(f"  title: {info.title}")
            print(f"  tags: {info.tags}")
        except Exception as e:
            print(f"  Error: {e}")

        # ── env.action_space ──────────────────────────────────────────────
        print(f"\n--- env.action_space ---")
        try:
            actions = env.action_space
            print(f"  Type: {type(actions)}")
            for action in actions:
                print(f"  {action.name:20s} | is_complex: {action.is_complex()}")
        except Exception as e:
            print(f"  Error: {e}")

        # ── env.observation_space (before any step) ───────────────────────
        print(f"\n--- env.observation_space (initial) ---")
        try:
            obs = env.observation_space
            print(f"  Type: {type(obs)}")
            print(f"  Value: {obs}")
            if obs:
                attrs = [x for x in dir(obs) if not x.startswith('_')]
                print(f"  Attributes: {attrs}")
                for attr in attrs:
                    try:
                        val = getattr(obs, attr)
                        if not callable(val):
                            print(f"    obs.{attr} = {val}")
                    except:
                        pass
        except Exception as e:
            print(f"  Error: {e}")

        # ── Take one step, observe result ─────────────────────────────────
        print(f"\n--- Taking first action: ACTION1 ---")
        try:
            result = env.step(GameAction.ACTION1)
            print(f"  Result type: {type(result)}")
            print(f"  Result: {result}")
            if result:
                attrs = [x for x in dir(result) if not x.startswith('_')]
                for attr in attrs:
                    try:
                        val = getattr(result, attr)
                        if not callable(val):
                            print(f"    result.{attr} = {val}")
                    except:
                        pass
        except Exception as e:
            print(f"  Error: {e}")

        # ── observation_space after step ──────────────────────────────────
        print(f"\n--- env.observation_space (after step) ---")
        try:
            obs2 = env.observation_space
            print(f"  {obs2}")
            print(f"  Changed from initial: {str(env.observation_space) != str(obs)}")
        except Exception as e:
            print(f"  Error: {e}")

        # ── Test each action ───────────────────────────────────────────────
        print(f"\n--- Testing each action (which ones change state?) ---")
        try:
            env.reset()
            for action in env.action_space:
                obs_b = str(env.observation_space)
                d = {"x": 32, "y": 32} if action.is_complex() else {}
                env.step(action, data=d)
                obs_a = str(env.observation_space)
                changed = obs_b != obs_a
                print(f"  {action.name:25s} -> {'CHANGED ✅' if changed else 'no change ❌'}")
        except Exception as e:
            print(f"  Error: {e}")

        return env.observation_space

    # ── STEP 2: Full exploration ───────────────────────────────────────────

    def explore_game(self, game_id: str, n_episodes: int = 5, max_actions: int = 200):
        """Auto-explore a game, logging every state transition."""
        print(f"\n{'='*60}")
        print(f"EXPLORING: {game_id} | {n_episodes} eps x {max_actions} actions")
        print(f"{'='*60}")

        for ep in range(n_episodes):
            print(f"\n--- Episode {ep+1}/{n_episodes} ---")
            arc = arc_agi.Arcade()
            env = arc.make(game_id)
            if env is None:
                continue

            wins = 0
            for step in range(max_actions):
                # Get state BEFORE action
                obs_b = env.observation_space
                obs_b_str = str(obs_b)

                # Choose random action
                actions = env.action_space
                if not actions:
                    break
                action = random.choice(actions)
                d = {"x": random.randint(0, 63), "y": random.randint(0, 63)} if action.is_complex() else {}

                # Take action
                result = env.step(action, data=d)

                # Get state AFTER action
                obs_a_str = str(env.observation_space)
                changed = obs_b_str != obs_a_str

                # Log transition
                t = {
                    "episode": ep, "step": step,
                    "action": action.name,
                    "action_data": d,
                    "state_before": obs_b_str[:300],
                    "state_after": obs_a_str[:300],
                    "state_changed": changed,
                    "game_state": str(result.state) if result and hasattr(result, 'state') else "unknown",
                    "levels_completed": getattr(result, 'levels_completed', 0) if result else 0,
                }
                self.logs[game_id].append(t)
                self.action_effects[game_id][action.name + ("_c" if changed else "_u")] += 1
                if changed:
                    self.state_changes[game_id].append(t)

                if result and hasattr(result, 'state') and result.state == GameState.WIN:
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
        print(f"\n📊 {game_id}: {changed}/{total} = {changed/total*100:.1f}% state change rate")
        print(f"  (Low % = most actions do nothing = why random agents fail!)\n")
        effects = self.action_effects[game_id]
        names = set(k.replace("_c","").replace("_u","") for k in effects)
        print(f"  Action effectiveness:")
        for a in sorted(names):
            c = effects.get(a+"_c", 0); u = effects.get(a+"_u", 0); t = c+u
            pct = c/t*100 if t > 0 else 0
            print(f"    {a:25s}: {pct:5.1f}% {'█'*int(pct/5)} ({c}/{t})")

    # ── STEP 3: Save ──────────────────────────────────────────────────────

    def save_all(self):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        for gid in self.logs:
            path = f"game_logs/{gid}_{ts}.json"
            with open(path, "w") as f:
                json.dump({
                    "game_id": gid, "timestamp": ts,
                    "total_transitions": len(self.logs[gid]),
                    "state_changes": len(self.state_changes[gid]),
                    "action_effects": dict(self.action_effects[gid]),
                    "sample_transitions": self.logs[gid][:500],
                    "sample_state_changes": self.state_changes[gid][:100],
                }, f, indent=2)
            print(f"✅ Saved: {path}")
