# Binder Publication Dependency and License Record

This record governs only the documentation-maintenance process that generates the
audited FXD binder PDFs. The exact build-time versions are pinned in
`requirements-binder.txt`; publication automation may not substitute newer or
unbounded versions.

| Package | Pinned version | License | Publication use | Redistribution and binary implications |
|---|---:|---|---|---|
| ReportLab | 5.0.0 | BSD 3-Clause | Creates the page layout and PDF volumes. | The selected release is installed as a pure-Python wheel. If the package is redistributed, its copyright, conditions, and disclaimer must accompany source or binary distributions as required by the license. The generated PDFs do not contain the ReportLab package. |
| pypdf | 6.14.2 | BSD 3-Clause | Rebuilds the combined volume, imports outlines, fixes metadata, and performs structural preflight. | The selected release is pure Python. Binary redistribution requires reproduction of the copyright, conditions, and disclaimer in accompanying materials. The generated PDFs do not contain the pypdf package. |
| Pillow | 12.3.0 | MIT-CMU | Decodes the approved repository logo while ReportLab builds the PDFs. | Platform wheels contain compiled image-codec support. This repository does not commit or redistribute the wheel or its native libraries. Any future bundled generator/runtime must receive a separate inventory of Pillow's bundled codec libraries and preserve the MIT-CMU notice. The PDFs contain only rendered logo pixels, not Pillow binaries. |
| charset-normalizer | 3.4.9 | MIT | Exact transitive dependency of the selected ReportLab release. | Some platform wheels use compiled mypyc extensions. This repository does not commit or redistribute those wheels. A future bundled generator/runtime must preserve the MIT copyright and permission notice. |

## Commercial and distribution boundary

All four packages permit commercial use under their recorded permissive licenses.
That observation is not a blanket approval to redistribute their packages or native
dependencies. The publication workflow installs them transiently, produces PDFs,
and commits only the PDFs and their SHA-256 manifest. No package wheel, shared
library, source archive, credential, customer CAD, or private engineering dataset is
part of the binder publication output.

The approved FXD logo is the only raster input. The generator reads no STEP data and
does not call an AI provider or external service. Any future dependency, packaging
change, font embedding, or native-code redistribution requires a new licensing and
security review before publication.

## Authoritative license sources

- ReportLab 5.0.0: project `LICENSE.txt` (BSD 3-Clause) and <https://pypi.org/project/reportlab/5.0.0/> release metadata.
- pypdf 6.14.2: <https://github.com/py-pdf/pypdf/blob/6.14.2/LICENSE>
- Pillow 12.3.0: <https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE>
- charset-normalizer 3.4.9: <https://github.com/jawah/charset_normalizer/blob/3.4.9/LICENSE>

The license record is reviewed together with the exact pins whenever a dependency
version changes.
