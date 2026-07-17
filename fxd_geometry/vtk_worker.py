"""Native VTK render worker used by the unified Windows workbench."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import logging
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import Thread

from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkRenderWindowInteractor

from .vtk_viewer import VtkSceneController
from .workbench import load_step_for_workbench


logger = logging.getLogger("fxd.vtk_worker")


def _write(message: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(message, sort_keys=True) + "\n")
    sys.stdout.flush()


def _read_commands(commands: Queue[dict[str, object]]) -> None:
    for line in sys.stdin:
        try:
            command = json.loads(line)
            if isinstance(command, dict):
                commands.put(command)
        except json.JSONDecodeError as exc:
            _write({"event": "error", "message": f"invalid worker command: {exc}"})
    commands.put({"command": "shutdown"})


def run(source: Path, expected_sha256: str, title: str) -> int:
    before = source.read_bytes()
    if sha256(before).hexdigest() != expected_sha256:
        raise RuntimeError("source SHA-256 changed before VTK worker import")
    document = load_step_for_workbench(source)
    render_window = vtkRenderWindow()
    render_window.SetWindowName(title)
    render_window.SetSize(1, 1)
    render_window.SetPosition(-32000, -32000)
    interactor = vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    interactor.Initialize()
    scene = VtkSceneController(render_window, interactor, document)
    scene.fit()
    after = source.read_bytes()
    if after != before or sha256(after).hexdigest() != expected_sha256:
        raise RuntimeError("source STEP bytes changed during VTK worker import")

    commands: Queue[dict[str, object]] = Queue()
    Thread(target=_read_commands, args=(commands,), daemon=True).start()

    def process_commands(_caller: object, _event: object) -> None:
        while True:
            try:
                request = commands.get_nowait()
            except Empty:
                return
            command = str(request.get("command", ""))
            request_id = request.get("request_id")
            try:
                if command == "fit":
                    scene.fit()
                elif command == "standard_view":
                    scene.standard_view(str(request["view"]))
                elif command == "set_wireframe":
                    scene.set_wireframe(bool(request["enabled"]))
                elif command == "set_transparent":
                    scene.set_transparent(bool(request["enabled"]))
                elif command == "set_visible":
                    scene.set_visible(bool(request["enabled"]))
                elif command == "set_review_geometry":
                    raw_items = request.get("items", [])
                    if not isinstance(raw_items, list):
                        raise ValueError("review geometry items must be a list")
                    scene.set_review_geometry(tuple(raw_items))
                elif command == "set_orbit":
                    scene.set_orbit(bool(request["enabled"]))
                elif command == "set_navigation_mode":
                    scene.set_navigation_mode(str(request["mode"]))
                elif command == "select":
                    scene.select(str(request["identity"]))
                elif command == "render":
                    scene.render()
                elif command == "benchmark":
                    result = scene.benchmark(int(request.get("frames", 20)))
                    _write({
                        "event": "response", "request_id": request_id,
                        "average_render_ms": result.average_render_ms,
                        "frames_per_second": result.frames_per_second,
                    })
                elif command == "shutdown":
                    interactor.TerminateApp()
                    return
                else:
                    raise ValueError(f"unsupported worker command {command!r}")
                if request_id is not None and command != "benchmark":
                    _write({"event": "response", "request_id": request_id})
            except Exception as exc:
                logger.exception("VTK worker command failed")
                _write({
                    "event": "error", "request_id": request_id,
                    "message": str(exc),
                })

    interactor.AddObserver("TimerEvent", process_commands)
    interactor.CreateRepeatingTimer(16)
    diagnostics = scene.diagnostics()
    _write({
        "event": "ready", "title": title,
        "backend": diagnostics.backend,
        "actor_count": diagnostics.actor_count,
        "actor_identities": sorted(scene.actors),
        "selection_identities": sorted(set(scene.actors) | set(scene.selection_aliases)),
        "point_count": diagnostics.point_count,
        "triangle_count": diagnostics.triangle_count,
    })
    interactor.Start()
    render_window.Finalize()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("expected_sha256")
    parser.add_argument("title")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    try:
        return run(args.source, args.expected_sha256, args.title)
    except Exception as exc:
        logger.exception("native VTK worker failed")
        _write({"event": "fatal", "message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
