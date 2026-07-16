# Local Engineering Workbench

Launch the Windows desktop shell from the repository root with:

```powershell
.\.venv\Scripts\python.exe scripts\fxd-app.py
```

Choose **Import STEP** and select a `.step` or `.stp` file. FXD first tries
the neutral product contract for the full review workflow. When a normal
vendor STEP file is outside that small metadata contract, the workbench uses
the real OCP kernel directly, retains the original source bytes and SHA-256,
imports the B-Rep, and displays its tessellated faces in the 3D canvas.

Drag on the canvas to rotate the view. The direct viewer is intentionally an
engineering-review entry point: it does not modify customer CAD, infer a
fixture, or claim validation, certification, or production approval. Files
with no usable solid geometry fail closed with an import error.
