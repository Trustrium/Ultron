"""System monitoring + process control via psutil."""
from __future__ import annotations
import datetime as _dt


def _psutil():
    import psutil
    return psutil


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} PB"


def system_info() -> str:
    """One-shot snapshot: CPU, RAM, disk, battery, uptime."""
    p = _psutil()
    try:
        cpu = p.cpu_percent(interval=0.5)
        vm = p.virtual_memory()
        disk = p.disk_usage("C:\\" if _is_windows() else "/")
        boot = _dt.datetime.fromtimestamp(p.boot_time())
        uptime = _dt.datetime.now() - boot
        hrs = int(uptime.total_seconds() // 3600)
        mins = int((uptime.total_seconds() % 3600) // 60)

        lines = [
            f"CPU: {cpu:.0f}% used",
            f"RAM: {vm.percent:.0f}% used ({_fmt_bytes(vm.used)} / {_fmt_bytes(vm.total)})",
            f"Disk C: {disk.percent:.0f}% used ({_fmt_bytes(disk.free)} free of {_fmt_bytes(disk.total)})",
            f"Uptime: {hrs}h {mins}m",
        ]
        try:
            bat = p.sensors_battery()
            if bat is not None:
                plugged = "charging" if bat.power_plugged else "on battery"
                lines.append(f"Battery: {bat.percent:.0f}% ({plugged})")
        except Exception:
            pass
        return "\n".join(lines)
    except Exception as e:
        return f"System info failed: {e}"


def _is_windows() -> bool:
    import os
    return os.name == "nt"


def top_processes(n: int = 5, by: str = "memory") -> str:
    """Top N processes by 'memory' or 'cpu'."""
    p = _psutil()
    n = max(1, min(int(n), 15))
    try:
        procs = []
        for proc in p.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
            try:
                info = proc.info
                procs.append(info)
            except Exception:
                continue
        key = "cpu_percent" if by == "cpu" else "memory_percent"
        procs.sort(key=lambda x: x.get(key) or 0, reverse=True)
        lines = [f"Top {n} processes by {by}:"]
        for pr in procs[:n]:
            mem = pr.get("memory_percent") or 0
            cpu = pr.get("cpu_percent") or 0
            lines.append(f"  {pr.get('name','?')} (pid {pr.get('pid')}): "
                         f"{mem:.1f}% RAM, {cpu:.1f}% CPU")
        return "\n".join(lines)
    except Exception as e:
        return f"Process list failed: {e}"


def find_process(name: str) -> str:
    p = _psutil()
    q = (name or "").lower().strip()
    if not q:
        return "Provide a process name."
    matches = []
    for proc in p.process_iter(["pid", "name"]):
        try:
            if q in (proc.info.get("name") or "").lower():
                matches.append((proc.info["pid"], proc.info["name"]))
        except Exception:
            continue
    if not matches:
        return f"No running process matching '{name}'."
    lines = [f"Processes matching '{name}':"]
    for pid, nm in matches[:10]:
        lines.append(f"  {nm} (pid {pid})")
    return "\n".join(lines)


def kill_process(name: str) -> str:
    """Terminate all processes matching a name. Destructive — confirm first."""
    p = _psutil()
    q = (name or "").lower().strip()
    if not q:
        return "Provide a process name."
    killed = []
    for proc in p.process_iter(["pid", "name"]):
        try:
            if q in (proc.info.get("name") or "").lower():
                proc.terminate()
                killed.append(f"{proc.info['name']} (pid {proc.info['pid']})")
        except Exception:
            continue
    if not killed:
        return f"No process matching '{name}' to terminate."
    return "Terminated: " + ", ".join(killed)
