

Markdown  
\# Implementation Specification: Local Prototype for Agentic CAD Blueprint Sandbox

This document provides a comprehensive blueprint and structured implementation steps for an AI coding agent to develop a local Proof of Concept (POC) consisting of a Python (FastAPI) backend and a Flutter desktop frontend (supporting both Linux and Windows platforms). The goal is to ingest, interpret, and visually manipulate 2D structural and 50 Hz electrical infrastructure data locally.

\---

\#\# 1\. System Topology and Architecture

The local prototype functions via high-performance localhost loopback communications. Heavy file conversion, computational geometry calculations, and data serialization are handled by a local Python server, while user interaction, affine spatial manipulations (zooming/panning), and vector path rendering are executed natively via the Flutter desktop subsystem.

\+---------------------------------------+ localhost:8000 \+-----------------------------------------+  
| FLUTTER DESKTOP APP | \> | LOCAL PYTHON BACKEND | | (Linux / Windows Architecture Core) | | (FastAPI Service) | | | \< | |  
| \+---------------------------------+ | JSON Metadata | \+-----------------------------------+ |  
| | Interactive Canvas | | & Static Render | | ODA CLI Subprocess Converter | |  
| | (CustomPainter / Zoom / 3 Color)| | | \+-----------------------------------+ |  
| \+---------------------------------+ | | \+-----------------------------------+ |  
| | State & Network Layer | | | | ezdxf & shapely Parser Core | |  
| | (Dio / Riverpod) | | | \+-----------------------------------+ |  
| \+---------------------------------+ | | \+-----------------------------------+ |  
| | | | Agent Query Processor | |  
\+---------------------------------------+ \+-----------------------------------------+

\---

\#\# 2\. Backend Architecture Specification (FastAPI & Python 3.11+)

The backend processing environment must run locally, eliminating cloud storage or cloud run overheads for this phase. It uses command-line tools and geometric extraction libraries to generate clean JSON vectors.

\#\#\# Step 1: Local DWG-to-DXF Conversion Subprocess  
Because direct parsing of binary \`.dwg\` data requires proprietary engines, conversion to ascii \`.dxf\` format must be performed using a localized CLI wrapper around the Open Design Alliance (ODA) File Converter tool or similar headless native binaries.

\*   \*\*Execution Strategy:\*\* Python \`subprocess.run\` executes the native conversion binary.  
\*   \*\*Target Execution Command Structure:\*\*  
    \`\`\`python  
    import subprocess  
    import os

    def convert\_dwg\_to\_dxf(input\_file\_path: str, output\_dir: str) \-\> str:  
        \# Configuration matches paths for local installation variables (Linux/Windows)  
        converter\_path \= "/usr/bin/ODAFileConverter" if os.name \== "posix" else "C:\\\\Program Files\\\\ODA\\\\ODAFileConverter.exe"  
          
        args \= \[  
            converter\_path,  
            os.path.dirname(input\_file\_path),  
            output\_dir,  
            "ACAD2018", \# Target Output DXF version  
            "DXF",       \# Format specification  
            "0",         \# Recurse flag  
            "1",         \# Audit flag  
            os.path.basename(input\_file\_path)  
        \]  
          
        result \= subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)  
        if result.returncode \!= 0:  
            raise RuntimeError(f"ODA Converter Failure: {result.stderr}")  
              
        expected\_dxf \= os.path.join(output\_dir, os.path.basename(input\_file\_path).replace(".dwg", ".dxf"))  
        return expected\_dxf  
    \`\`\`

\#\#\# Step 2: Layer Extraction and Geometric Analysis (\`ezdxf\` & \`shapely\`)  
The parsed DXF structure is evaluated entity by entity. Specific target layers are isolated to ensure discrete categorization of structural blocks versus 50 Hz power networks.

\*   \*\*Extraction Mechanics:\*\*  
    \*   Open file stream via \`ezdxf.readfile()\`.  
    \*   Query modelspace target elements using structural and electrical identifiers: \`doc.modelspace().query('LINE POLYLINE LWPOLYLINE MTEXT TEXT')\`.  
    \*   Group shapes by layer properties (e.g., \`LAYER\_STREET\_PLAN\`, \`LAYER\_BLOCK\_SEPARATION\`, \`LAYER\_50HZ\_CABLING\`).  
\*   \*\*Coordinate Stabilization & Scale Preservation:\*\*  
    To safeguard structural scale ratios during mapping transformations on the frontend canvas, the backend must calculate the precise geometric bounding box (\`Bounds\`) of all compiled elements.  
    Let $X\_{min}$, $Y\_{min}$, $X\_{max}$, $Y\_{max}$ represent the absolute boundaries of the drawing. The data points are normalized to a local coordinate grid, and these dimensions are passed within the root JSON payload metadata block.

\`\`\`python  
from shapely.geometry import LineString, Polygon  
import ezdxf

def parse\_dxf\_geometry(dxf\_path: str) \-\> dict:  
    doc \= ezdxf.readfile(dxf\_path)  
    msp \= doc.modelspace()  
      
    payload \= {  
        "metadata": {"min\_x": 0.0, "min\_y": 0.0, "max\_x": 0.0, "max\_y": 0.0},  
        "elements": \[\]  
    }  
      
    all\_coords \= \[\]  
      
    for entity in msp.query('LINE LWPOLYLINE'):  
        layer \= entity.dxf.layer  
        if entity.dxftype() \== 'LINE':  
            start \= (entity.dxf.start.x, entity.dxf.start.y)  
            end \= (entity.dxf.end.x, entity.dxf.end.y)  
            all\_coords.extend(\[start, end\])  
            payload\["elements"\].append({  
                "type": "line",  
                "layer": layer,  
                "coordinates": \[start, end\]  
            })  
        elif entity.dxftype() \== 'LWPOLYLINE':  
            pts \= \[(pt\[0\], pt\[1\]) for pt in entity.get\_points()\]  
            all\_coords.extend(pts)  
            payload\["elements"\].append({  
                "type": "polyline",  
                "layer": layer,  
                "coordinates": pts  
            })  
              
    if all\_coords:  
        xs \= \[p\[0\] for pt in all\_coords\]  
        ys \= \[p\[1\] for pt in all\_coords\]  
        payload\["metadata"\] \= {  
            "min\_x": min(xs),  
            "min\_y": min(ys),  
            "max\_x": max(xs),  
            "max\_y": max(ys)  
        }  
    return payload

### **Step 3: Local REST API Layout (FastAPI)**

The application surface exposes functional endpoints for rapid synchronous query and transmission of local data blocks.

* POST /api/v1/prototype/upload: Ingests binary local raw .dwg payloads, writes temporary buffers, executes conversion, processes geometry, and yields structural JSON metadata directly.  
* POST /api/v1/prototype/agent/query: Interacts directly with the localized LLM agent environment. Accepts a tracking ID and an execution query string to analyze JSON arrays on disk against target planning regulations.

## **3\. Frontend Desktop Architecture Specification (Flutter)**

The GUI handles coordinate system projection and user event collection.

### **Step 1: Affine Matrix Bounding Conversions**

The core mathematical challenge is drawing absolute WCS (World Coordinate System) canvas points accurately onto local pixels while respecting view changes from scrolling or resizing. The viewport transformation maps arbitrary design units into rendering points without losing relative scale accuracy.  
Flutter natively isolates this bounding logic inside the InteractiveViewer module using an transformation matrix (Matrix4). The CustomPainter reads state offsets directly from the parent matrix, rendering design vectors inside a localized bounded screen space.

### **Step 2: Scale-Preserving Rendering Engine (CustomPainter)**

The painter transforms drawing layers based on user parameters, mapping specific layers to specific colors.

* **Color Classification Scheme:**  
  * LAYER\_STREET\_PLAN $\\rightarrow$ Rendered via thin neutral lines (Grey: 0xFF9E9E9E).  
  * LAYER\_BLOCK\_SEPARATION $\\rightarrow$ Rendered via medium distinct layout bounds (White/Black based on context).  
  * LAYER\_50HZ\_CABLING $\\rightarrow$ Highlighted through structural application lines drawn in three distinct colors depending on voltage class or subsystem criteria (e.g., Red: 0xFFD32F2F, Blue: 0xFF1976D2, Green: 0xFF388E3C).

Dart  
import 'package:flutter/material.dart';

class CADElement {  
  final String type;  
  final String layer;  
  final List\<Offset\> points;

  CADElement({required this.type, required this.layer, required this.points});  
}

class BlueprintPainter extends CustomPainter {  
  final List\<CADElement\> elements;  
  final Map\<String, double\> scaleMetadata;

  BlueprintPainter({required this.elements, required this.scaleMetadata});

  @override  
  void paint(Canvas canvas, Size size) {  
    final double minX \= scaleMetadata\['min\_x'\] ?? 0.0;  
    final double minY \= scaleMetadata\['min\_y'\] ?? 0.0;  
    final double maxX \= scaleMetadata\['max\_x'\] ?? 1.0;  
    final double maxY \= scaleMetadata\['max\_y'\] ?? 1.0;

    final double mapWidth \= maxX \- minX;  
    final double mapHeight \= maxY \- minY;

    // Preserve aspect ratio inside local bounds  
    final double scaleX \= size.width / mapWidth;  
    final double scaleY \= size.height / mapHeight;  
    final double nativeScale \= scaleX \< scaleY ? scaleX : scaleY;

    for (var element in elements) {  
      final paint \= Paint()  
        ..strokeWidth \= 1.5  
        ..style \= PaintingStyle.stroke;

      // Color logic mapped to specific infrastructural layers  
      if (element.layer.contains('50HZ\_PRIMARY')) {  
        paint.color \= Colors.red;  
      } else if (element.layer.contains('50HZ\_SECONDARY')) {  
        paint.color \= Colors.blue;  
      } else if (element.layer.contains('50HZ\_CONTROL')) {  
        paint.color \= Colors.green;  
      } else if (element.layer.contains('STREET')) {  
        paint.color \= Colors.grey;  
      } else {  
        paint.color \= Colors.white38;  
      }

      if (element.points.length \< 2) continue;

      for (int i \= 0; i \< element.points.length \- 1; i++) {  
        // Project absolute CAD coordinates into native Canvas pixel addresses  
        Offset src \= Offset(  
          (element.points\[i\].dx \- minX) \* nativeScale,  
          size.height \- ((element.points\[i\].dy \- minY) \* nativeScale), // Invert Y-axis for standard CAD alignment  
        );  
        Offset dest \= Offset(  
          (element.points\[i \+ 1\].dx \- minX) \* nativeScale,  
          size.height \- ((element.points\[i \+ 1\].dy \- minY) \* nativeScale),  
        );  
        canvas.drawLine(src, dest, paint);  
      }  
    }  
  }

  @override  
  bool shouldRepaint(covariant BlueprintPainter oldDelegate) \=\>  
      oldDelegate.elements \!= elements;  
}

## **4\. Operational AI Agent Code Generation Prompts**

### **Module 1: Backend Parsing Service Engine**

"Write a complete FastAPI endpoint in Python utilizing ezdxf and shapely. The endpoint must receive a local file pathway to a converted DXF drawing file, extract lines and open polyline properties from layers named 'STREET\_PLAN', 'BLOCK\_SEPERATE', and '50HZ\_LINE'. It must parse the mathematical global coordinate points, determine the overall minimum and maximum X and Y envelope boundaries of all compiled primitives, and return a single structured JSON payload containing the metadata envelope boundaries along with an array of the normalized coordinate entities sorted by layer."

### **Module 2: Frontend Network Client Configuration**

"Develop a Flutter architecture data client implementation utilizing the dio networking package. It must connect to http://localhost:8000/api/v1/prototype/upload and post an absolute local .dwg file pathway structure as a multipart form data asset payload. Create a class object model mapper framework that handles parsing the returned JSON coordinate layer array into strongly typed Dart classes, handling the mapping of point structures into UI native coordinate Offset arrays."

### **Module 3: Zoomable Viewport Canvas Integration**

"Write a Flutter widget component that displays an interactive graphical CAD workspace canvas. The canvas structure must be nested directly within an InteractiveViewer widget configured with clear minimum and maximum zoom coefficients ranging from 0.1 to 25.0 to handle standard zoom and pan mechanics seamlessly. Wire the component lifecycle methods directly into a custom implementation of the provided BlueprintPainter class, passing the raw coordinate offset array inputs and scaling metadata properties to enable accurate hardware-accelerated rendering."