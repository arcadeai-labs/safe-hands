"""Fake `lerobot` for running IliaLarchenko/robot_MCP with no hardware attached.

robot_MCP imports lerobot at module import time (robot_controller.py, config.py). This module
installs just enough of `lerobot.*` into sys.modules for those imports to succeed and for a
RobotController to "connect", read a plausible observation, and accept actions. Nothing here
talks to a motor. Call install() BEFORE importing anything from robot_MCP.
"""
import sys
import types

import numpy as np

MOTORS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

# Normalized start pose. Through robot_MCP's default MOTOR_NORMALIZED_TO_DEGREE_MAPPING this is
# roughly: shoulder_pan 90 deg (facing forward), arm folded upright, gripper closed.
START_NORM = {"shoulder_pan": 3.9, "shoulder_lift": -89.4, "elbow_flex": 96.5,
              "wrist_flex": 0.0, "wrist_roll": 100.0, "gripper": 31.0}


class _FakeBus:
    def disable_torque(self): pass
    def enable_torque(self): pass


class FakeFollower:
    """Stands in for SO100Follower / SO101Follower / LeKiwiClient."""
    sent_actions: list = []

    def __init__(self, cfg=None):
        self.cfg = cfg
        self.connected = False
        self.positions = dict(START_NORM)
        self.bus = _FakeBus()

    def connect(self, *a, **k): self.connected = True
    def disconnect(self, *a, **k): self.connected = False

    def get_observation(self):
        obs = {}
        for name, v in self.positions.items():
            obs[f"{name}.pos"] = v          # so100 / so101 key shape
            obs[f"arm_{name}.pos"] = v      # lekiwi key shape
        obs["front"] = np.zeros((4, 4, 3), dtype=np.uint8)   # one tiny "camera" frame
        return obs

    def send_action(self, action: dict):
        FakeFollower.sent_actions.append(dict(action))
        for k, v in action.items():
            name = k.replace("arm_", "").replace(".pos", "")
            if name in self.positions:
                self.positions[name] = float(v)
        return action


class _AnyConfig:
    def __init__(self, *a, **k):
        for key, val in k.items():
            setattr(self, key, val)


def install():
    """Register fake lerobot modules. Idempotent."""
    if "lerobot" in sys.modules and getattr(sys.modules["lerobot"], "_safe_hands_fake", False):
        return
    def mod(name, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items(): setattr(m, k, v)
        sys.modules[name] = m
        return m
    root = mod("lerobot"); root._safe_hands_fake = True
    root.robots = mod("lerobot.robots", Robot=FakeFollower)
    mod("lerobot.robots.so100_follower", SO100Follower=FakeFollower, SO100FollowerConfig=_AnyConfig)
    mod("lerobot.robots.so101_follower", SO101Follower=FakeFollower, SO101FollowerConfig=_AnyConfig)
    mod("lerobot.robots.lekiwi", LeKiwiClient=FakeFollower, LeKiwiClientConfig=_AnyConfig)
    root.cameras = mod("lerobot.cameras")
    root.cameras.opencv = mod("lerobot.cameras.opencv")
    mod("lerobot.cameras.opencv.configuration_opencv", OpenCVCameraConfig=_AnyConfig)
