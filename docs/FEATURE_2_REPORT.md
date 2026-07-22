# Feature 2 — Local CAD Sandbox: Implementation Report

Source spec: `tmp/feature_2.md` (= `docs/LOCAL_SANDBOX_SPEC.md`, "option A").
Related evaluation: [CAD_ENGINE_EVALUATION.md](CAD_ENGINE_EVALUATION.md)
(Open CASCADE — rejected for the 2D pipeline; kept on the 3D roadmap).

## 1. Spec → implementation mapping

| Spec item | Status | Where / notes |
| :--- | :--- | :--- |
| Local FastAPI backend, no cloud dependency | ✅ already existed | `backend/app` runs fully local (`make backend`); mock agent = zero-credential mode |
| DWG→DXF via local CLI subprocess | ✅ already existed, improved | Spec assumed ODA-only; we run LibreDWG `dwg2dxf` first with ODA as fallback (DEPLOYMENT.md §3). **Basic DXF upload needs no converter at all** |
| ezdxf + shapely extraction, bounds metadata in payload | ✅ already existed | `extraction/`; `DataLayerPayload.bounds` = the spec's min/max envelope |
| REST endpoints (`/prototype/upload`, `/prototype/agent/query`) | ✅ equivalent, different names | Kept our richer `/api/v1/jobs` lifecycle (async status polling instead of one blocking call) + `/jobs/{id}/chat` |
| **Zoom/pan canvas: InteractiveViewer, 0.1×–25×** | ✅ **new this feature** | `frontend/lib/features/canvas/plan_canvas.dart` — `InteractiveViewer` (minScale 0.1, maxScale 25, unbounded pan), double-tap resets the view, hint overlay bottom-right |
| **Semantic layer→color classification** | ✅ **new this feature** | `layerColor()` in `plan_canvas.dart` — spec's literal layer names (`LAYER_STREET_PLAN`, `LAYER_50HZ_CABLING`) don't exist in real DB plans, so classification is keyword-based on real layer names (see §2) |
| Scale-preserving projection, Y-axis flip | ✅ already existed | Uniform fit-to-viewport scale + CAD-Y-up flip in `_PlanPainter` |
| Typed Dart element model ↔ JSON mapper | ✅ already existed | `frontend/lib/models/job.dart` (`Geometry` ≙ spec's `CADElement`) |
| Dio multipart client | ✅ already existed | `frontend/lib/core/api_client.dart` |
| Linux + Windows desktop targets | ✅ scaffolded / ⚠️ partially verified | Flutter project builds for linux/windows/macos/web; only Linux is exercised. Backend on Windows would need a Windows `dwg2dxf`/ODA binary (LibreDWG ships win32/win64 release zips) |

## 2. Layer color classes (adapted to real DB drawings)

First matching rule wins (keyword, case-insensitive, German-aware):

| Rule (layer name contains) | Color | Meaning |
| :--- | :--- | :--- |
| `leitung`, `kabel`, `cable`, `50hz` | red `#D32F2F` | 50 Hz cabling — strongest highlight |
| `eea`, `lst` | blue `#1976D2` | electrical equipment / signalling |
| `planung` | green `#388E3C` | new planning |
| `rückbau` | orange `#F57C00` | demolition/removal |
| `bestand`, `gleis`, `strasse`, `street`, `bue` | grey `#9E9E9E` | existing context |
| `frame`, `legende`, `logo`, `layout` | white24 | sheet furniture, dimmed |
| *anything else* | stable 6-color fallback palette | unknown layers stay distinguishable |

Verified against `Kreuzungsplan.dwg`'s real layers: `+EB_Planung_EEA-Leitungen`
→ red, `+EB_Planung_EEA` → blue, `+EB_Planung` → green, `+EB_Rückbau` →
orange, `Bestand` → grey, `+EB_Layout_Frame`/`+EB_Legende` → dimmed.

## 3. Open CASCADE decision (user request)

Evaluated as candidate engine; **rejected for this feature** — the
open-source OCCT core reads STEP/IGES only (DXF/DWG are paid add-ons) and a
B-Rep kernel has no notion of drawing layers/annotations, which carry our
compliance signal. Full analysis and the 3D roadmap where OCCT *does* fit:
[CAD_ENGINE_EVALUATION.md](CAD_ENGINE_EVALUATION.md).

## 4. How to test

```bash
make backend      # terminal 1
make frontend     # terminal 2
```

Drop `backend/data/samples/DB/Kreuzungsplan.dwg` (or any `.dxf` directly —
"basic DXF" needs no converter): the crossing plan renders with the semantic
colors; scroll/pinch zooms 0.1×–25×, drag pans, double-tap resets.

Checks: `flutter analyze` and `flutter test` clean; backend pytest 3/3.

## 5. Known limitations / next steps

- Stroke width zooms with the view (lines get fat at 25×) — cosmetic; fix is
  scale-aware `strokeWidth` via the `TransformationController` listener.
- A color-legend overlay for the classes is not drawn yet.
- Block-reference content (`INSERT`/`ATTRIB`) still isn't extracted into the
  *data layer* (top parser task) — but it **is now visible** via the
  server-side render view (`GET /jobs/{id}/render` + the canvas
  Render/Vectors toggle), so nothing is hidden from the user anymore.
- Windows run of the *backend* untested; frontend project is scaffolded for it.
