"""Native VTK render worker used by the unified Windows workbench."""
from __future__ import annotations

import argparse
import ctypes
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
    face_picking_enabled = False
    press_position: tuple[int, int] | None = None
    user32 = None
    native_window_id = 0
    original_window_proc = 0
    window_proc_callback = None
    if sys.platform == "win32":
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_ssize_t,
        ]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        native_window_id = int(user32.FindWindowW(None, title) or 0)

    def remember_press(_caller: object, _event: object) -> None:
        nonlocal press_position
        press_position = tuple(int(value) for value in interactor.GetEventPosition())

    def report_face_pick(_caller: object, _event: object) -> None:
        nonlocal press_position
        release = tuple(int(value) for value in interactor.GetEventPosition())
        start = press_position
        press_position = None
        if not face_picking_enabled:
            return
        if start is not None and sum(
            (left - right) ** 2 for left, right in zip(start, release)
        ) > 25:
            return
        face_identity = scene.pick_face(*release)
        _write({"event": "face_picked", "face_identity": face_identity})

    def process_commands(_caller: object, _event: object) -> None:
        nonlocal face_picking_enabled
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
                    if isinstance(request_id, int):
                        # The fixture is much larger than the synthetic source
                        # product. Fit after installing every review actor so
                        # the first accepted visual-review frame is inspectable.
                        scene.fit()
                        _write({
                            "event": "response", "request_id": request_id,
                            "review_actor_count": len(scene.review_actor_identities),
                            "rendered": True,
                        })
                elif command == "set_orbit":
                    scene.set_orbit(bool(request["enabled"]))
                elif command == "set_navigation_mode":
                    scene.set_navigation_mode(str(request["mode"]))
                elif command == "set_face_picking":
                    face_picking_enabled = bool(request["enabled"])
                elif command == "set_size":
                    width, height = int(request["width"]), int(request["height"])
                    if width <= 0 or height <= 0:
                        raise ValueError("render size must be positive")
                    render_window.SetSize(width, height)
                    scene.render()
                elif command == "preview_orientation":
                    scene.preview_orientation(
                        tuple(float(value) for value in request["right"]),
                        tuple(float(value) for value in request["front"]),
                        tuple(float(value) for value in request["up"]),
                    )
                elif command == "simulate_face_click_for_acceptance":
                    x, y = int(request["x"]), int(request["y"])
                    if x < 0 or y < 0:
                        width, height = render_window.GetSize()
                        x, y = width // 2, height // 2
                    _write({"event": "face_picked", "face_identity": scene.pick_face(x, y)})
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
                if request_id is not None and command not in {"benchmark", "set_review_geometry"}:
                    _write({"event": "response", "request_id": request_id})
            except Exception as exc:
                logger.exception("VTK worker command failed")
                _write({
                    "event": "error", "request_id": request_id,
                    "message": str(exc),
                })

    interactor.AddObserver("TimerEvent", process_commands)
    interactor.CreateRepeatingTimer(16)
    if user32 is not None and native_window_id:
        # The VTK window lives in a separate process and is reparented into Qt,
        # so Qt cannot observe its mouse events. Subclass the child window long
        # enough to report short face-selection clicks, then delegate every
        # message to VTK's original window procedure so orbit/pan/zoom remain
        # native and unchanged.
        window_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_ssize_t,
        )
        native_press: list[tuple[int, int] | None] = [None]

        def _client_point(lparam: int) -> tuple[int, int]:
            return (
                ctypes.c_short(lparam & 0xFFFF).value,
                ctypes.c_short((lparam >> 16) & 0xFFFF).value,
            )

        def _window_proc(
            hwnd: int, message: int, wparam: int, lparam: int,
        ) -> int:
            if message == 0x0201:  # WM_LBUTTONDOWN
                native_press[0] = _client_point(lparam)
            elif message == 0x0202:  # WM_LBUTTONUP
                release = _client_point(lparam)
                start = native_press[0]
                native_press[0] = None
                width, height = render_window.GetSize()
                if (face_picking_enabled and start is not None
                        and sum((left - right) ** 2
                                for left, right in zip(start, release)) <= 25
                        and 0 <= release[0] < width
                        and 0 <= release[1] < height):
                    face_identity = scene.pick_face(
                        release[0], height - 1 - release[1],
                    )
                    _write({
                        "event": "face_picked",
                        "face_identity": face_identity,
                    })
            return int(user32.CallWindowProcW(
                original_window_proc, hwnd, message, wparam, lparam,
            ))

        window_proc_callback = window_proc_type(_window_proc)
        original_window_proc = int(user32.SetWindowLongPtrW(
            native_window_id, -4, window_proc_callback,
        ) or 0)
        if not original_window_proc:
            window_proc_callback = None
    if not original_window_proc:
        # Portable fallback: run before the active camera style can consume the
        # event. Do not register this in addition to the Win32 hook, because a
        # duplicated pick could be interpreted as the next wizard step.
        interactor.AddObserver("LeftButtonPressEvent", remember_press, 1.0)
        interactor.AddObserver("LeftButtonReleaseEvent", report_face_pick, 1.0)
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
    if user32 is not None and native_window_id and original_window_proc:
        user32.SetWindowLongPtrW(native_window_id, -4, original_window_proc)
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
