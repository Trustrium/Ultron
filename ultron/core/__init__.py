"""Ultron Core — Commander, planning and verification.

Unique to Ultron by Trustrium: every command goes through
Understand -> Plan -> Execute -> Verify -> Report (sir).
"""
from .commander import UltronCommander, parse_command, build_plan

__all__ = ["UltronCommander", "parse_command", "build_plan"]
