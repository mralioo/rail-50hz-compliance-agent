# **Engineering Process Automation in Railway 50 Hz Electrical Planning: A Strategic Venture Pivot and Business Development Report**

## **Analysis of Core Industry Bottlenecks and Technical Vulnerabilities**

Modern railway infrastructure development in the European and German-speaking (DACH) sectors is undergoing a major technological shift. Under modernization initiatives led by infrastructure managers such as DB InfraGO AG, over a hundred years of legacy, locally operated interlockings are being systematically decommissioned.1 These outdated systems are being replaced by modern digital interlocking (DSTW) technologies controlled from central operating centers.1 This transition is illustrated by the regional modernization of the Harz-Weser network, which covers the strategic routes 1810 and 1812 between Seesen and Herzberg.1 This modernization demands highly synchronized electrical planning for auxiliary power, station lighting, and level crossing safety installations (Bahnübergangssicherungsanlagen or BÜSA).1  
Within this technical domain, 50 Hz auxiliary power planning represents a critical, resource-intensive bottleneck.3 Electrical planning engineers must design, calculate, and document low-voltage connections that interface with public grid networks (VNB) and railway-owned energy systems managed by entities such as DB Energie GmbH.1 Reviewing the technical files of active railway electrification projects, such as the Level Crossing (BÜ) Herzberg Schloß at chainage km 116,626 on route 1812, reveals several distinct process vulnerabilities.1 These vulnerabilities are highly repetitive and present clear opportunities for software-driven automation.

### **Manual Document Compilation and the Template Drift Trap**

A central requirement for securing planning approval is the generation of a comprehensive explanatory report (Erläuterungsbericht).1 This document describes the existing electrical infrastructure, details the planned technical alterations, lists active regulatory standards, and defines installation rules.1 Under guidelines such as Ril 813.01 and Ril 813.04, these reports must follow highly rigid, standardized outlines.4  
In typical engineering practices, planners compile these documents manually, often copying past reports and modifying project metadata such as line numbers, chainages, and DB project codes.1 This manual workflow introduces significant operational risks:

* **The Template Drift Trap**: Engineering offices frequently rely on local directories of past documents, which leads to the citation of outdated, deprecated, or invalid regulatory codes. For example, the Herzberg Schloß project files cite the historical earthing guideline Ril 954.0107.1 However, administrative directives from the Federal Railway Authority (EBA) have formally withdrawn Ril 954.0107 as an accepted technical rule.8 Citing retired guidelines results in immediate plan rejection during formal reviews.5  
* **The Overhead of Redundant Technical Text**: Large portions of these explanatory reports consist of standard technical text. Planners must repeatedly transcribe standard cable pulling forces (such as ![][image1] for non-flexible cables and ![][image2] for flexible cables under tension) and cable bending radii (12-fold diameter for multi-core and 15-fold for single-core cables).1 Manually re-entering these values for every project consumes highly skilled engineering hours that would be better spent on complex design challenges.

### **Cross-Document Data Discrepancies**

A single 50 Hz railway planning package requires a multi-part documentation suite. This suite includes the narrative explanatory report 1, crossing drawings (Kreuzungspläne) 1, overview schematics (Übersichtspläne) 1, earthing layouts (Erdungspläne) 1, and mathematical cable calculations (Netzberechnungen).1 When engineering changes occur, planners must manually update every occurrence of the affected parameters across all documents.  
For example, a technical change in the main feed for the level crossing at Herzberg Schloß (km 116,626) required replacing the existing ![][image3] copper cable with a new NYY-O ![][image4] cable to operate under a TT-system topology.1 This change also required modifying the upstream protection at the meter cabinet (ZAS DB Energie) at km 116,630.1 Specifically, the fuse had to be downsized from 35 A to 25 A to maintain selective coordination.1  
Ensuring that the cable cross-section (![][image5]), the fuse rating (25 A Diazed / D02), and the system topology (TT-system) match perfectly across the narrative report, the Übersichtsplan, the Erdungsplan, and the Excel-based mathematical calculation sheets is a major source of human error.1 A single mismatch between a CAD drawing and a Word-based report triggers a validation failure, resetting the review timeline.

### **Stakeholder Negotiation and Regulatory Coordination**

The transition from design to physical implementation requires intensive coordination between the design firm, the infrastructure manager (DB InfraGO), the energy provider (DB Energie), and local distribution network operators (VNB).1 These technical negotiations often revolve around complex compliance requirements, such as Technical Connection Conditions (TAB) and guidelines like the T107.1  
As demonstrated in technical communications for Herzberg Schloß, a planner had to present two alternative design pathways 1:

1. **Alternative 1 (Full Reconstruction)**: Dismantling the existing meter (DB 501147\) and building a new, fully T107-compliant meter connection column (ZAS DB Fahrwege).1 This path required coordinating complex selectivity calculations with the VNB, resulting in significant administrative overhead and scheduling delays.  
2. **Alternative 2 (Grandfathering / Bestandsschutz)**: Utilizing the existing ZAS and replacing the 35 A fuse (-1F6) with a 25 A fuse-switch-disconnector while increasing the downstream cable cross-section to NYY-O ![][image4].1 This pragmatic compromise required explicit approvals from the regional 50 Hz team (50 Hz Hannover Süd) and the operations engineering manager (ALV-Fahrweg).1

Planners spend days drafting emails, chasing internal approvals, and manually drawing up justifications for these deviations. Software tools currently do not automate the modeling or the generation of the standardized justification text required to obtain these approvals.

### **The Administrative Cost of the EBA Planprüfung Loop**

Under the VV BAU-STE administrative directives, every signaling, telecommunication, and electrical installation (STE-Anlage) must undergo a rigorous Planprüfung (plan inspection) by an EBA-certified inspection expert (Prüfsachverständiger) before construction can begin.11  
The duration of this process and its high standard of scrutiny create a major bottleneck for projects, as summarized in the following table:

| Process Characteristic | Impact and Detail | Source |
| :---- | :---- | :---- |
| **Typical Review Duration** | Approximately 16 weeks from the submission of complete, compliant planning documents. | 14 |
| **Plausibility Checking (PlaZ)** | Manual verification of data consistency between schematic symbols and narrative descriptions. | 2 |
| **Error Consequences** | Typographical or reference errors require a revised submission, restarting the multi-week review clock. | 13 |
| **Site Inconsistencies** | Construction firms frequently discover design errors on-site, requiring costly operational change orders. | 9 |

These recurring issues highlight a clear market need. The industry requires an automated software platform that can ingest calculation data, cross-reference it against active regulatory guidelines, and auto-generate consistent, pre-validated planning files. This solution would significantly reduce the high rate of plan rejections.

## **Market Dimensions and Competitive Positioning**

To evaluate the commercial viability of a software platform designed to automate these workflows, the market size, competitive landscape, and regulatory barriers must be systematically mapped.1

### **Sizing the German-Speaking (DACH) Railway Planning Software Market**

The target market is characterized by stable public funding, long-term infrastructure investment cycles, and highly specialized engineering service providers.3 The market sizing calculations are structured as follows:

* **Total Addressable Market (TAM)**: Represents the total software and digital engineering tool expenditure potential within the DACH railway infrastructure sector.1 Driven by German federal initiatives like "Digital Schiene Deutschland" and major corridor renovations, DB InfraGO’s annual modernization budgets exceed several billion euros. The addressable software and digital planning tool budget for engineering firms servicing this market is estimated at approximately €150,000,000 annually.  
* **Serviceable Available Market (SAM)**: Focused specifically on the electrical engineering, low-voltage (50 Hz), lighting, and auxiliary power infrastructure segments of the rail sector.3 This segment represents approximately €40,000,000 of the software procurement potential, distributed across specialized engineering offices and DB's internal planning divisions.  
* **Serviceable Obtainable Market (SOM)**: Target segment comprising small-to-medium-sized engineering bureaus (such as E+B Planungsbüro) and independent 50 Hz planning engineers who require immediate, low-barrier automation tools to improve their submission speed and quality.1 This initial market size is estimated at €4,500,000.

### **Competitive Landscape and Niche Identification**

The existing software environment is characterized by powerful general-purpose design suites and niche railway signaling tools, leaving a clear gap in specialized 50 Hz railway electrical design automation.

| Competitor Category | Key Players | Strengths | Vulnerabilities and Gaps | Source |
| :---- | :---- | :---- | :---- | :---- |
| **General Low-Voltage Calculation Tools** | Siemens SIMARIS Suite (design, project, curves), ABB DOC | Industry-standard load-flow and short-circuit calculations; automatically dimensions cables and selects real products based on VDE standards. | Lacks rail-specific regulatory context; cannot auto-generate DB-compliant *Erläuterungsberichte* or check compliance with DB Ril 813 or Ril 819\. | 16 |
| **Digital Signaling & Track Planning Platforms** | DB InfraGO PlanPro Tools, GEO-Planer, Signalling Engineering Toolbox | Highly integrated with DB's digital track database (AVANI); standardizes signaling and interlocking planning data formats via XML. | Exclusively optimized for signaling logic (LST) and track geometry; does not address auxiliary 50 Hz power networks. | 2 |
| **Project Commissioning Software** | Schüßler-Plan IBN-DOKU | Digitizes the preparation of commissioning documents (Inbetriebnahmeunterlagen) for STE projects. | Focuses on late-stage commissioning and handovers; does not automate early design and calculation tasks. | 21 |
| **Status Quo: Manual Workflows** | MS Word, Excel, generic CAD blocks | High flexibility; zero software purchasing cost for standard tools. | High rate of copy-paste errors; "template drift" leads to regulatory rejections; significant engineering overhead. | 1 |

### **Sector-Specific Barriers and Regulatory Constraints**

Developing and launching a software solution in this niche requires navigating several industry-specific challenges, colloquially referred to as "hidden traps" 1:

* **Proprietary Railway Data Schemas**: DB InfraGO increasingly mandates the use of proprietary data structures like the PlanPro XML format (.planpro) for rail-related designs.2 A 50 Hz utility planning tool must remain compatible with these standards, ensuring seamless data flow between track geometry layouts and electrical schematics.  
* **Liability and Certification under the VV BAU-STE**: Software tools used to automate calculations or produce design files must demonstrably incorporate the accepted rules of technology (Anerkannte Regeln der Technik).11 If an algorithm generates incorrect cable dimensions or selects non-compliant protective devices, the engineering firm face significant liability risks.23  
* **Transition from Plan-Centric to Data-Centric Processes**: The industry is moving away from purely document-based layouts toward integrated Building Information Modeling (BIM) workflows.7 A successful product must not simply generate flat PDF or Word reports; it must store technical parameters in structured, machine-readable formats (such as database schemas or JSON) to support future export into broader CAD, BIM, and GIS tools.17

## **Strategic Pivot and Business Validation Plan**

Based on the technical bottlenecks and market dynamics, the proposed business pivot focuses on transitioning from a general-purpose automation concept to a dedicated B2B SaaS platform: **Rail50Hz.ai**. This platform is designed to automate compliance check-ups, explanatory report generation, and data synchronization for railway electrical planners.1  
The following 10-week validation and development plan aligns this pivot with structured market testing and product validation methodologies.1

### **Week 1: Strategic Pivot and Stakeholder Mapping**

The venture must establish its core thesis: automating 50 Hz railway electrical engineering workflows to reduce administrative overhead and EBA approval delays.1

* **Core Activities**: Analyze the technical files of the level crossing project at Herzberg Schloß (Project G.016123626) to map every manual step in the design and approval process.1  
* **Deliverables**: Create a detailed map of the key stakeholders involved in project approvals, including the Planning Engineer (Planersteller), the Technical Specialist (Fachspezialist), the Local Infrastructure Manager (ALV-Fahrweg), and the EBA-certified Planprüfung Inspector.3

### **Week 2: Market Analysis and Competitive Positioning**

The team must systematically evaluate the commercial viability of the proposed B2B SaaS platform within the DACH region.1

* **Core Activities**: Quantify the number of active railway electrical engineering firms in Germany, Austria, and Switzerland. Identify the software licensing budgets of these target clients.  
* **Deliverables**: Establish realistic TAM, SAM, and SOM targets.1 Create a competitive positioning matrix highlighting how **Rail50Hz.ai** addresses the gaps left by Siemens SIMARIS, PlanPro, and manual document creation.2

### **Week 3: Business Model Modeling and Enterprise Unit Economics**

This week focuses on designing a pricing and subscription model that aligns with the procurement habits of infrastructure engineering firms.1

* **Core Activities**: Evaluate the financial viability of a per-seat, tiered B2B SaaS subscription model compared to a usage-based, per-project licensing model.  
* **Deliverables**: Define pricing tiers tailored to different firm sizes, aiming for high Customer Lifetime Value (CLV) to Customer Acquisition Cost (CAC) ratios to support enterprise sales cycles:

| Subscription Tier | Target Customer | Features Included | Pricing Structure | Source |
| :---- | :---- | :---- | :---- | :---- |
| **Professional (Seat-Based)** | Boutique engineering bureaus and independent 50 Hz planners. | SIMARIS XML parser, automated Word-based *Erläuterungsbericht* compiler, standard VDE compliance checks. | €250 / user / month (Billed annually) | 1 |
| **Enterprise (Bureau-Wide)** | Mid-to-large engineering firms and DB's internal planning teams. | Advanced compliance checking (including DB Ril 813 and Ril 819 modules), multi-format data synchronization, automated CAD parameter validation. | Custom annual contract (Starting at €15,000 / year) | 4 |

### **Week 4: MVP Scope Definition and AI Prototyping**

The objective is to define a highly focused MVP scope and build a functional web-based prototype using modern development frameworks.1

* **Core Activities**: Map the exact technical parameters from a Siemens SIMARIS design export to the corresponding fields in a standardized DB-style explanatory report template.1  
* **Deliverables**: Build a functional web interface using tools like Lovable or Claude. The tool must allow users to upload a SIMARIS Excel output and automatically generate a formatted Word document, eliminating manual copy-paste steps.18

The system architecture and data transformation flow for this MVP are outlined below:

   
                 │  
                 ▼ (Automated Extraction)  
  ──────►  
   • Nominal Voltage (Un \= 230/400 V)         • Verify active VDE & DB Ril guidelines  
   • Connection Load (P \= 3 kVA)             • Flag deprecated codes (e.g., Ril 954.0107)  
   • Selected Cable (NYY-O 2x10 mm²)  
   • Short-Circuit Current (Ik \= 10 kA)  
                 │  
                 ▼ (Template Engine Merging)  
   
                 │  
                 ▼ (Instant Download)  
 

The mapping of technical parameters from the input file to the compiled output document is structured as follows:

| Target Parameter | SIMARIS Source Cell / Field | Compiled Word Document Insertion Point | Source |
| :---- | :---- | :---- | :---- |
| **System Voltage (![][image6])** | "Un \= 400 V / 230 V" | Section 3.4 (Netzverhältnisse): "Netzform BÜ-Anlage: TT-System 1L N PE AC 50 Hz 230 V" | 1 |
| **Connection Load** | "3.0 kVA" or "10.0 kVA" | Section 3.5 (Stromversorgungsanlage): "Die Anschlussleitung beträgt 3 kVA." | 1 |
| **Main Feed Cable** | "Cu (1x10/10/10)" / "KL1.2" | Section 3.5: "Einspeisung... wird mit einem Kabel vom Typ NYY-O ![][image4] ausgeführt." | 1 |
| **Upstream Protection** | "SLTS 1.28" / "In \= 25 A" | Section 3.5: "Der Schutz der Stromkreise erfolgt durch eine Schmelzsicherung... von 25 A." | 1 |
| **Short-Circuit Rating** | "10,000 A" / "Kurzschlussbelastung" | Section 3.7 (Blitz- und Überspannungsschutz): Validates protective device ratings against calculated 10 kA fault levels. | 1 |

### **Week 5: Structured User Testing and Problem Validation**

This week focuses on conducting structured interviews with target users to validate the core problem and test the MVP prototype.1

* **Core Activities**: Recruit 5 active railway electrical planning engineers. Walk them through the automated report generation tool without guiding their actions, observing how they interact with the interface.1  
* **Deliverables**: Gather direct qualitative feedback. Structure the interviews around the principles of "The Mom Test" to assess the true severity of their current workflow pain points 1:  
  1. *Validation of current pain*: "How do you currently ensure that cable changes in your calculations are accurately updated across your narrative reports and CAD drawings?" 1  
  2. *Validation of regulatory friction*: "Describe your last experience with a plan-check rejection due to an outdated guideline reference. How much time did it take to resolve?" 9  
  3. *Commitment Ask*: Secure a clear sign of commitment from the interviewees, such as a signed Letter of Intent (LOI) to pilot the tool on an upcoming project or a small deposit for early platform access.1

### **Week 6: Go-to-Market Execution and Marketing Channels**

The goal of this phase is to design and launch target acquisition campaigns to drive 100 relevant users to the platform.1

* **Core Activities**: Launch cold outreach campaigns on networks like LinkedIn and specialist engineering portals targeting professionals with titles like "Elektroplaner 50 Hz", "Planungsingenieur Bahn", and "Projektingenieur TGA".15  
* **Deliverables**: Create high-value content explaining the risks of manual citation errors and outdated standards (such as Ril 954.0107) in railway design.8 Track key conversion metrics, including landing page visits, demo sign-ups, and SIMARIS file uploads.18 Conduct follow-up interviews with users who visit the page but do not convert to identify friction points.1

### **Week 7: Technical Refinement and Data Integration**

This phase is dedicated to expanding the parser's capabilities and refining document output based on user testing data.1

* **Core Activities**: Enhance the parsing algorithm to handle complex cable networks, multiple power sources, and various operating modes calculated within SIMARIS design.18  
* **Deliverables**: Integrate standard document styles from key clients like DB Station\&Service and DB InfraGO to ensure generated reports are immediately client-ready.4 Build robust export features that output data in both standard Word templates and structured JSON formats.19

### **Week 8: Financial Modeling and Capitalization**

The team must build a comprehensive 3-year bottom-up financial model to track the venture's growth.1

* **Core Activities**: Calculate operational costs, including hosting, document parsing APIs, and regular regulatory database updates. Build sales-capacity models to project growth as team members are added.  
* **Deliverables**: Create a detailed 3-year cash-flow projection. Determine the capital required for a pre-seed funding round, using early user metrics and pilot commitments to validate the business's potential to investors.1

### **Week 9: Legal Architecture and Safety Compliance**

This week focuses on structuring the venture's legal framework, addressing intellectual property, software liability, and data protection regulations.1

* **Core Activities**: Draft B2B Terms of Service that clarify liability boundaries: the software must be explicitly positioned as a design assistant tool, leaving ultimate engineering and calculations liability with the licensed engineer of record.23  
* **Deliverables**: Create GDPR-compliant data processing agreements to reassure clients that proprietary project information and DB-related data are handled securely. Secure intellectual property rights for the platform's proprietary parsing algorithms.

### **Week 10: Graduation, Demonstration, and Piloting**

The validation cycle culminates in presenting the platform to potential investors and industry partners.1

* **Core Activities**: Prepare a live technical demonstration showcasing the platform's core value proposition: converting raw SIMARIS files into complete, compliant explanatory reports in seconds.1  
* **Deliverables**: Deliver a presentation on Demo Day detailing key validation metrics, including the TAM/SAM/SOM breakdown, target user feedback, and signed pilot commitments.1 Secure early customer agreements to fund the next phase of development.

## **Strategic Synthesis and Actionable Venture Recommendations**

For a prospective founder pivoting into the railway electrical planning automation market, success depends on balancing technical utility with a clear understanding of the sector's regulatory constraints. The following recommendations provide a practical framework for building a high-value product:

### **Focus on Document Automation and Regulatory Checks**

The platform should focus on a clear, high-value initial feature: parsing Siemens SIMARIS output files to auto-populate compliant Explanatory Reports.1 The tool must parse key design metrics—such as system configurations (e.g., TT-systems vs. TN-C-S networks), main cable cross-sections (e.g., NYY-O ![][image4]), and protective device ratings (e.g., 25 A fuses)—and insert them directly into standard Word templates.1 This immediate utility saves planners hours of manual work and provides a compelling reason to adopt the tool.

### **Implement a Cloud-Updated Compliance Database**

To address the risk of outdated references, the platform should feature an integrated, cloud-updated compliance database.1 This database will track active regulations, including VDE standards, DB corporate guidelines (Ril 813 and Ril 819), and EBA administrative directives.1  
By automatically checking user inputs against active standards, the platform can flag retired guidelines—such as the withdrawn Ril 954.0107—and suggest the correct current replacements.8 This automated validation acts as a pre-submission check, helping engineering firms catch formatting and compliance errors before documents are sent to formal EBA reviews.12

### **Build Cross-Document Verification Logic**

To reduce manual coordination errors, the platform should implement cross-document verification features. The system should compare data across different project files—such as the narrative report, calculation sheets, and CAD drawing files (via DXF/DWG formats)—to ensure complete consistency.1  
If a planner modifies a key specification (for example, updating a connection load or cable type), the software will automatically flag any mismatch between the CAD drawings and the text reports.1 This automated consistency check reduces the risk of typographical errors that can delay project approvals.9

### **Manage Engineering Liability**

Given the strict regulatory environment of railway technology, the platform must clearly manage its liability boundaries. The software should be marketed as an "AI-Powered Compliance Assistant" rather than an autonomous decision-maker. The Terms of Service must state that the tool simplifies document compilation and checks for formatting errors, while the final review, validation, and liability under VV BAU-STE remain with the human engineer of record.12 This clear division of responsibility protects the software venture from direct liability risks while still delivering significant value to the engineering firm.23

#### **Works cited**

1. EeaX 1812.116,6.03.pdf  
2. Digitale LST-Planung \- DB InfraGO, accessed July 13, 2026, [https://www.dbinfrago.com/web/schienennetz/dienstleistende/planpro/digitale\_lst\_planung-11161508](https://www.dbinfrago.com/web/schienennetz/dienstleistende/planpro/digitale_lst_planung-11161508)  
3. Planungsleitfaden ZIM V4.0 \- Deutsche Bahn AG, accessed July 13, 2026, [https://infoplattform-personenbahnhoefe.deutschebahn.com/resource/blob/13116610/26300e127b105e8e1a560e673b0de1ce/TM-2024-07-I-ISI1-Planungsleitfaden-ZIM-V4-0-data.pdf](https://infoplattform-personenbahnhoefe.deutschebahn.com/resource/blob/13116610/26300e127b105e8e1a560e673b0de1ce/TM-2024-07-I-ISI1-Planungsleitfaden-ZIM-V4-0-data.pdf)  
4. Erneuerung von Elektrotechnischen Anlagen in Personenverkehrsanlagen (PVA), accessed July 13, 2026, [https://infoplattform-personenbahnhoefe.deutschebahn.com/resource/blob/7716742/e3e3b7fff8c5ba67e62a47a22108b7bc/42\_Erneuerung-von-Elektrotechnischen-Anlagen-data.pdf](https://infoplattform-personenbahnhoefe.deutschebahn.com/resource/blob/7716742/e3e3b7fff8c5ba67e62a47a22108b7bc/42_Erneuerung-von-Elektrotechnischen-Anlagen-data.pdf)  
5. Fachplaner LST \- TOPEOPLE GROUP, accessed July 13, 2026, [https://www.topeople.de/glossar-seite/fachplaner-lst](https://www.topeople.de/glossar-seite/fachplaner-lst)  
6. 50-Hz-Netz \- DB Energie GmbH, accessed July 13, 2026, [https://www.dbenergie.de/dbenergie-de/netzbetreiber/50hznetz](https://www.dbenergie.de/dbenergie-de/netzbetreiber/50hznetz)  
7. DB InfraGO AG \- Elektrische Energieanlagen; NS-Versorgungskonzept 50Hz, accessed July 13, 2026, [https://infoplattform-personenbahnhoefe.deutschebahn.com/pbhf/regelwerk/Elektrische\_Energieanlagen\_NS-Versorgungskonzept\_50Hz-7718868](https://infoplattform-personenbahnhoefe.deutschebahn.com/pbhf/regelwerk/Elektrische_Energieanlagen_NS-Versorgungskonzept_50Hz-7718868)  
8. EBA \- Fachmitteilungen \- Außerkraftsetzung der DB Richtlinie 954.0107 als „Anerkannte Regel der Technik“ \- Eisenbahn-Bundesamt, accessed July 13, 2026, [https://www.eba.bund.de/SharedDocs/Fachmitteilungen/DE/2025/10\_2025\_Ausserkraftsetzung\_der\_DB\_Richtlinie\_954\_0107\_als\_Anerkannte\_Regel\_der\_Technik.html](https://www.eba.bund.de/SharedDocs/Fachmitteilungen/DE/2025/10_2025_Ausserkraftsetzung_der_DB_Richtlinie_954_0107_als_Anerkannte_Regel_der_Technik.html)  
9. Tag der Bauüberwachung, accessed July 13, 2026, [https://netz-bauueberwachung.deutschebahn.com/resource/blob/13105430/c08e0372ba7bd97530c7b648ab11cd56/2024-10-15\_Praesentation-Tag-der-BUeW-data.pdf](https://netz-bauueberwachung.deutschebahn.com/resource/blob/13105430/c08e0372ba7bd97530c7b648ab11cd56/2024-10-15_Praesentation-Tag-der-BUeW-data.pdf)  
10. Anlage 5.7.6 zu den Nutzungsbedingungen der DB InfraGO AG 2027 Kategoriespezifische Basisleistungen und weitere Leistungen der I, accessed July 13, 2026, [https://www.dbinfrago.com/resource/blob/13700006/923d4de8d0e9ab774d5a8124caaa567f/INB-2027-Anlage-5-7-6-data.pdf](https://www.dbinfrago.com/resource/blob/13700006/923d4de8d0e9ab774d5a8124caaa567f/INB-2027-Anlage-5-7-6-data.pdf)  
11. Anhänge zur VV BAU STE 5.0 \- Eisenbahn-Bundesamt, accessed July 13, 2026, [https://www.eba.bund.de/SharedDocs/Downloads/DE/Infrastruktur/AllgemeineVorschriften/VV\_BAU\_STE/VV\_BAU\_STE\_5\_0/22\_VV\_BAU\_STE\_5\_0\_Anh\_pdf.pdf?\_\_blob=publicationFile\&v=2](https://www.eba.bund.de/SharedDocs/Downloads/DE/Infrastruktur/AllgemeineVorschriften/VV_BAU_STE/VV_BAU_STE_5_0/22_VV_BAU_STE_5_0_Anh_pdf.pdf?__blob=publicationFile&v=2)  
12. Verwaltungsvorschrift für die Überwachung der Erstellung von Signal-, Telekommunikations- und Elektrotechnischen Anlagen (VV BAU-STE) \- Eisenbahn-Bundesamt, accessed July 13, 2026, [https://www.eba.bund.de/SharedDocs/Downloads/DE/Infrastruktur/AllgemeineVorschriften/VV\_BAU\_STE/22\_VV\_BAU\_STE\_5\_1.pdf?\_\_blob=publicationFile\&v=2](https://www.eba.bund.de/SharedDocs/Downloads/DE/Infrastruktur/AllgemeineVorschriften/VV_BAU_STE/22_VV_BAU_STE_5_1.pdf?__blob=publicationFile&v=2)  
13. Verwaltungsvorschrift für die Überwachung der Erstellung von Signal-, Telekommunikations- und Elektrotechnischen Anlagen (VV BAU-STE) \- Eisenbahn-Bundesamt, accessed July 13, 2026, [https://www.eba.bund.de/SharedDocs/Downloads/DE/Infrastruktur/AllgemeineVorschriften/VV\_BAU\_STE/VV\_BAU\_STE\_5\_0/22\_VV\_BAU\_STE\_5\_0.pdf?\_\_blob=publicationFile\&v=2](https://www.eba.bund.de/SharedDocs/Downloads/DE/Infrastruktur/AllgemeineVorschriften/VV_BAU_STE/VV_BAU_STE_5_0/22_VV_BAU_STE_5_0.pdf?__blob=publicationFile&v=2)  
14. Kabelquerungen bei der Bahn \- BZNB, accessed July 13, 2026, [https://www.bznb.de/fileadmin/dokumente/\_Praesentationen\_Breitbandgipfel/08\_20191022\_Breitbandgipfel\_Ns\_-\_Bahnquerungen\_DB.pdf](https://www.bznb.de/fileadmin/dokumente/_Praesentationen_Breitbandgipfel/08_20191022_Breitbandgipfel_Ns_-_Bahnquerungen_DB.pdf)  
15. Planungsingenieur:in elektrische Energieanlagen 50Hz \- DB Jobs, accessed July 13, 2026, [https://db.jobs/de-de/Suche/Planungsingenieur-in-elektrische-Energieanlagen-50Hz-13734964](https://db.jobs/de-de/Suche/Planungsingenieur-in-elektrische-Energieanlagen-50Hz-13734964)  
16. Florian Thom, Freelance Technischer Produktdesigner | Stahlbau, Treppenbau, Elektro- & HLS-Planung auf www.freelancermap.at, accessed July 13, 2026, [https://www.freelancermap.at/profil/freelance-technischer-produktdesigner-stahlbau-treppenbau-elektro-und-hls-planung](https://www.freelancermap.at/profil/freelance-technischer-produktdesigner-stahlbau-treppenbau-elektro-und-hls-planung)  
17. SIMARIS Planungstools — Elektroplanungssoftware \- Siemens, accessed July 13, 2026, [https://www.siemens.com/de-de/products/simaris/](https://www.siemens.com/de-de/products/simaris/)  
18. Tutorial SIMARIS design \- Siemens, accessed July 13, 2026, [https://assets.new.siemens.com/siemens/assets/api/uuid:20509a8f-e976-4024-b7ff-79e5f0bc605d/Tutorial-SIMARIS-design-25-0-DE.pdf](https://assets.new.siemens.com/siemens/assets/api/uuid:20509a8f-e976-4024-b7ff-79e5f0bc605d/Tutorial-SIMARIS-design-25-0-DE.pdf)  
19. LST-Anlagen digital planen \- DB InfraGO, accessed July 13, 2026, [https://www.dbinfrago.com/resource/blob/11161554/ed01d939ba3488e9eb18f82c0b287142/planpro\_handbuch-data.pdf](https://www.dbinfrago.com/resource/blob/11161554/ed01d939ba3488e9eb18f82c0b287142/planpro_handbuch-data.pdf)  
20. Algorithmus für Planungswerkzeuge zur automatischen Planung von Signalen \- Qucosa \- TU Dresden, accessed July 13, 2026, [https://tud.qucosa.de/en/api/qucosa%3A91446/attachment/ATT-0/](https://tud.qucosa.de/en/api/qucosa%3A91446/attachment/ATT-0/)  
21. IBN SP Flyer 2020 RZ.indd \- Schüßler-Plan, accessed July 13, 2026, [https://www.schuessler-plan.de/datas/Brosch%C3%BCren/IBN%20SP%20Flyer%202020%20RZ%2002.pdf](https://www.schuessler-plan.de/datas/Brosch%C3%BCren/IBN%20SP%20Flyer%202020%20RZ%2002.pdf)  
22. Digitalisierung und Projektbeschleunigung als Systemlösung \- Digitale Schiene Deutschland, accessed July 13, 2026, [https://digitale-schiene-deutschland.de/Downloads/Fachartikel\_SIGNAL-DRAHT\_%28D3ip\_6-13%29.pdf](https://digitale-schiene-deutschland.de/Downloads/Fachartikel_SIGNAL-DRAHT_%28D3ip_6-13%29.pdf)  
23. Künstliche Intelligenz als Planprüfbehörde \- Baumeister, accessed July 13, 2026, [https://www.baumeister.de/kuenstliche-intelligenz-planpruefung/](https://www.baumeister.de/kuenstliche-intelligenz-planpruefung/)  
24. Aufgabenstellung zur Erfassung von Bauwerksdaten bei neu gebauten/instand gesetzten Hochwasserschutzanlagen \- Landestalsperrenverwaltung des Freistaates Sachsen, accessed July 13, 2026, [https://www.wasserwirtschaft.sachsen.de/download/ltv/AGS-HSA-Datenerfassung.pdf](https://www.wasserwirtschaft.sachsen.de/download/ltv/AGS-HSA-Datenerfassung.pdf)  
25. Ergänzende Regelwerke DB Personenbahnhöfe \- Informationsplattform Anlagentechnik, Bautechnik und ITK, accessed July 13, 2026, [https://infoplattform-personenbahnhoefe.deutschebahn.com/pbhf/regelwerk](https://infoplattform-personenbahnhoefe.deutschebahn.com/pbhf/regelwerk)  
26. SIMARIS configuration software \- Siemens, accessed July 13, 2026, [https://www.siemens.com/en-us/products/simaris/configuration/](https://www.siemens.com/en-us/products/simaris/configuration/)  
27. SIMARIS design \- basic handling | Sources, operating modes and cable dimensioning, accessed July 13, 2026, [https://resources.sw.siemens.com/de-DE/simaris-design-basic-handling-sources-webinar/](https://resources.sw.siemens.com/de-DE/simaris-design-basic-handling-sources-webinar/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF4AAAAaCAYAAAA+G+sUAAAEi0lEQVR4Xu2YeahVVRSHV/Mo2UBWVJZRUaSCQQM0vAxKtCyIaMAGLBGVkMKIyuqvoIhmG6AISyONzAQxbeIRNqeWKGrZP2UlKY1UZEStz7X3u+use+69vue73pDzwQ/e+e1zzjtnnbXXXvuKVGwvd6veVH2kuiCMVbSJa1V3pr/PVP2lOqU2XNEubld94I6/UE13xzsdV8n/b1rvpfpddX3wm3K8aqJqf+edo3rIHWeuUb2uel/1smpwcbiOd1X/Ot1WHJYL3VjW5MIZ9SxUHRrNDjNFtVq1bxxoxkipf/kfVGf7k8QC8pnUXpqFZaM7bsanqh9Vv6qOCmOHqWaq3lKdUByq4wjVomh2mKGqt1VHxoFWnK/6RvWdaqXqGdWJhTNEBqn+VF3uvF3FrrvVeY34WHWL2EdlpkQuU90RzRJuVo2PZgehSrygGpCOu2pDrSHjn41m4AaxoA0LPlm6OHhlEPg9VMvF7jOmOLzNgad0+ZLYSXZRPa26SCzgV0gva3yXtA78DLGAxTLxquo31d7Bj9DnwnCxtmu9ap/a8NbA59asEUNUr0Szg0yT+hIdy3NTulQvqR4UWzg3qR4W+6KZ+WI3ph575iT/uOBHyPjMPWLX8D8y25Lxd0mx1I1QfSl2L56f2fiEWIs3T3VMEmPdYrPzEqlxo9haxvWsX5eKXc8i+bhqT7FqsEBsjSLJTt56ZT9B8/+1WEYBQfxZih3IG1Ie+BeTf1LwIz7wtF5kPNedlTwCT1/cjE+kOLMOUp0ntsCvEZuVlDOg6yJYr4mtT/CI6ivV7umY9x0n9hzLxDo7OET1h2qJWCnhniQh51DP+w0WhsHBm636RewhgBauLPCch09L2gwfeKAuch0BI5itAn+66rloJggIieI/ChnL/c9w3tUl3sHJY6Z7PhfrwkiSzFNivXpbuU/sga5Mx7PS8eE9ZxhMY3xeoBlka2Su2LXs9loFnj1Fo00TH5UM95Dd3JtykWHx87MMBibvfucBTUB38JhRW4LXZ5hC3WJ1kfYwQzB4oJvScX6RY3vOMJjK+P7aMsoCz+z5SSyLpkrjwPOMZOBucSDBs9PtePLz5rICOfB+AWS2493rPCDw7wSPwP8dvD5DRvwj9vJ+18VCywNREuC6dMyC5lmqei94ZVBvy5gkdl/qdKPAU8cfi6aDbO9N4M91Hq1pbwLPuf0GU5U2z0PNIxtZwOBAsV0nv8hl+GibxbK1FdThMshmgsYLNQo8nUazNo3n703gu5yXS01HAn+x6kmpZTy/0zClaLc8tFtkV57yE1QrpHUPzwL9rdh64Xv3DLtkdsVlged/sZv2ra0HnwWa5/CwLyFIBzhvfPJGO+/o5D3qPO65Tmp7j8xMsXP3C/52QVD4wmQOpYMgl8EC94DYYsv0zzOiETmbs74vDvfAYl4W+FFSv/BlThMLer43/Tet8YfO44PTMvIh2Ljh0SpyTxKLPUs+l6Ti+rXOW5U8f88NYr+Q7tQQsFOjWdFe2LjE/r9iBzBW7Kfnih3M89L69/mKNsDOtqKioqKib/wHAXAaw9Z1q+4AAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF4AAAAaCAYAAAA+G+sUAAAELklEQVR4Xu2Ya6gVVRTHl5mVqWQWVqJx7UNi9ICCHlB09YOKSr7QVERKQtGgKILoeQkS8ov5REGRqwhR5BPRQo1LH8reb7QX9KHoBRWChfqh1u+u2Z119pk5Z473judymR/84c7aM/vM/c+atdcekZKe8rzqsOo91aRorKQgFqueSf6+S3VadWNluKQonlK9646/UT3rjvsdC6TvvdYXq06pHojiuRmgGhsHE5aqbnXHQ1WrVHe4WMzbqn+dnqwelsluLGhF1Rm1HFCNjIMt5mHVV6pL44FGjFLNFFso9kRjgaNSa9IO1UX+pAw+VP2hOqkaE41drepUHVFdXz1UA/d5MA62mJvEvBkdDzTiEdXnqg2qM5Jt/FuqT1R/qt4Uuy4v76seF3tYr0VjMEf1dBxM4THVkjjYQnjrSb5hyXF7Zag5qFNZxpORbXEwJxg/SPWxmPnTqodzG0/p4p/tC1CWN6umixl+v/SgxtcznjLUFgdzQp8Lt4i1Xd+pBleGu40PrVkW16lej4Mt5AmpLb33VJ3RBI2Mf1C1V/WpWPbSv+aBjA90iN3kyy6WJ+OfU811xyz034rN9YrqZtVGsRZvl1iSIMa6xN7YGVLhIdVvUlnQWeO4nkVyvdjaNVG1T2yN2q26ofvKAqhnPN3Ei+6Ym/tBNcLFsvDG03qR8fzDdycxjKcvrscHqkvcMb87QfWL6rjYGkU5g3fEzCJJrkpia1Tfqy5MjnmDFondx0eqZUn8StXfYusYpYQ5KSucQz0vhHrGk1Ge8WI3vTKKp+GNB+oi12IYZjYynpZ1WxxMwJC/pPqhkBTMf6eLLUyJXZHEDrkYfCbWhZEkgU1i/hQCE5MleRgidtNfxAMpkK0xr4pdz26vkfGrJXvTxEMlwz1kN3P7VpfFz79lMDyJsR/xUEa7oljo+gohy/jZql9V81yM14+bpk42Is14+ndaU37zUck2nt8hAwfGAwnUdLodTzA+lBUIxvsFkDYw7a3FeNpnD8afjWK9BiawmMS8IHaDHS4WssV/r8iCepvGcrE5qNNZxlPH18VBB9nejPH3uhitaTPGc24hYPz+OKjMUu2UyuIFvLLcCJ9GG0EdToNsDp8Vsoyn06jXplFqmjG+3cVC8rTUeBaSf8S2vxji4fgNqXyXuUCsy2Fx9P14GnQJP6nmS/q548R+N814ygu76vh+AsS5B3bUnq1iJl3mYux4iU11sWuT2FoXY86vpbL3CHSKncva1ivQqx4T++eZGNF20bf7XeI1qi1iD4aaTWt1uRtPI2Rz0M/Vw//zkqQbP0VqF77A7WKmh7npv9lX8L+EGA+clpEHwcaNGK0ic9LH/+7OpWRx/QkX+zKJ+Tl/FPtC2q/BsNviYEmxsJ7E/X/JeeA+ybdwl/Qy26Xx9/mSAmBnW1JSUlJybvwH3NML8AyuwOwAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF0AAAAZCAYAAABTuCK5AAAD10lEQVR4Xu2YWahOURTHlzGziMyZx8yJjN1IHoyZia4QpfAiIh7kBRmTWcqUkjwYMhUXGZKU6UEiIQoZQ5L4/6293fXt+w3nDr7u1fnVv77zP/tM66yz9tqfSExMGaQzdBi6D22HaibujvkXXIQaQZWgY9C+xN2paQvNhWoYbxC0wWxni8bQVugqdA6alri7VFENeguNcNu50C+o/N8RaRgsOtjqNTTQDsoCnaBnoglA+OK/iH7CZYEV0KPQTMUQ6Dn0EroL7YbaJ4zIDtehU2Z7rWgClOZs91SBnkKzAj8lzPQ9oZllhosGeIrx2omWmtrGK60wUReGZjpypOhB7wB1DE1DfahfaCaB12fQu4c7ygBzoAnuNxM4Ejmibc966DT0BtoIlTNjUsGgcsJrHu4AdaFbUJdwRxJuigZ9KHQJugFtgxrYQUnYAX0WPbYrtAjaC92B5rkxC6AT0APRl1vV+RVE7+8H9AqqA62Bjot2JQxgdWiL6DNeg5b8OTKfvqKxynFi2xgJHsgJrJXbbg19kIIXSEVL6IIklgE+0EmJ/uYfiwaOx/A8fOG7ROcYPngqekp+7c+Dejvflyueb6bz2Np9h2a7bXYZOdAZ6BN0BGro9jH470TnmF7OGyd6Tj/fsSd/4TwvnisSPDjM1IPQR6he4KeCJeS8aMAY8APQ1IQR6WGm8abHGK+H85ip6RgrOm6p8fiF0GOGW5jtocdM5dgBxpvovMXGa5LEK1FWi15gcrgjDbxpBn4/NCNxV0a4ouP12hivqfOuGC8Zo0XHMbs9TBZ6q4xH+OWwhFpYVjnWrlN8VrPcefgVhC+3SPAzzhNt1/i5eZaLXmC+8TJREToL3Rat54UhT/R6tYznH/Ke8ZLBxQnHDTOeD/pK4xEGPSwBvjyx7fP4oLOd9vj7WWa8IlEZ+im6COEKy+Pfvl9tZYIBPypaL/uIBrEwrd4m0etxYvY0c16mTPf1O2rQOSlaWL8LE3QmZLFh59At8PgJvpdoGcsafkj05j2cnPlwUQPfX/SBbHvJSTJZ4EJ8eYkadJZAi0+wqEHnyrPYjBRtz3ymc/nNNsrP8plgDefxYYvJG74s6bsPC1s9dhu8D5Y6tnfM8kwvbrpoMMYbr4Xz1hmP98cuia2fhV1S+JXlOm+U8Tjf0ON8VyJwwmTbxyDxzybbRaRjErRZCgbcwyV8mG2pYBfF+vpEdEnNnteWvGRwxco2kMH4JtqJ8L8b/ndEj2Lfz0n+ofE4T/Dr5gvwHv8GYbB3ip6L3lfRF8een39u+bGMVUxMTExMTExMTEzMf8JvYfzmNdPZjioAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGgAAAAZCAYAAADdYmvFAAAEPklEQVR4Xu2Ya6gVVRTHl700KhMzwrC6RmKG9hKzosdNhT5oKCVYYSFZFL1ICyMSIiSi6EFPBUVuRdmHEDSpLIhbiPSG3qXGhbAPZZQZFdqHWr/Wnnv2rDNzzpzj6Xo+7B/8uff8956ZPbP2rL32iCQSCRmlWqPaqtqkmpBvThxoVqpmhP+Xqb5VHVZrrsbFqg9Uv4e/i/PNQ854b0Scp1qvekfVr7oo19p9vKZ6OPzfo/pH7HlXZqpqm6pXNU71sthJ7or6DAVHiY2BdPBrvmmQc1U/qM4Jv2ep/pLaDO12esWebaMJWMdbqkuj38NVA6o/VcdG/v/JmaofVS+pvlLtzjcP8qHqSee9qNrovG6Fyf+cNxtxkFha2646OvJXiUX6QKS6V6U4QCyujOlW59+n2qM6xPndxrViwRnhGxrBTe0Su/FTIv+x4N0WeUWcqprkzQjewPO92YSyAC0QG9NC5y8Jfkt5fYg5S/WoapjqZNVJ+ebGnCH1OfxNsZue6XwPAaBv0QVHqz5STfENTSgL0FKxMRGomFuCf53zM65X/STW52bVPNUzqi9VT4lVVNz/BrHxUoCc9t+RBtmELMPxp4utzWtVn4qdD24XGzfnZA09PPhwjOoF1SVia9AD0uIa5OHgvaotYhFvBv3flnyKPFis5veBr0JZgJZLcYBuCv6Nzs9gxvLW0edjqfUbI7bObhYLwqFi90uf50MfOFusCuP4fqkVKLODx31mk2Os2LNjUmQQePploqjh+bQNg/terKKrCmmMYoMgcXFmzNW5HtUpC9DdUhwgHjh+o/WSWUyf153PW/CLWGGUwb7lj+g3XC52/D2Rd1zwGG8Mb5H3OsZVYgOe7BsqcIFYkAjwonxTS3Bzv3lTuUHsgVzpfNIMPg+xDHbz9HnI+Z+IvRUxT6v2OW+u2PG8NRm8gXgrIg8+k/qJ0BHYDw2opvmGilBwkC64adafdikL0BViD2SR8+8Mfq/zY9hj0Yf8H8NYSc8xBOhv580ROz7ejmQBuj/ygAC94bz95gTVDtWFkceixoJaBYLziljunS42K+M1qRUIEGWzp0fsgdzh/AfF8jpvSRlHSmsBom9Mtt5UDRCFU8egLufzDukt5l7VZc4rgjWHzWKcPvgcwyDbCRIBomoqgs87q53HJpXJ0YgsxbUboCzFVQ0Qqb5j9Il9WuGk/aqvVT+LXZx9TjNYc56V+oqPEv1d1RHObwbjYJEuOo6K8TvV8eE35TBr5sTBHsWcKHY/T0Qe4+XD5fuRB31ifePrXxO8+ZHXE7xHIo9zMj6+XHeEkWIXKVOzr65UVNy0D04G5a2fYUWwZvF2MFGya/PgCRbFRwyThnOuE6u42Mc1grSbbcYRD483/JvI+yJ470XeTrGswp6J0hmPVPq4WOWY7a0QY2ecBDzzPpf8fiqRSCQSiUQikUgkEk34F+eVBEBbYZsCAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEQAAAAZCAYAAACIA4ibAAAC60lEQVR4Xu2XS8hNURiGP+TOwP2WEJISJSll8EcYEHKboVzLgIlLhJKJa+SSa0qIDNxF7goZKPeBpBQhyYAQBryvby3nO5+9/7OPY3D077eewX7X+vfa/7vX/tZ3RHLVOfUDh8EjsAO0LB6ue7oKOoGG4BjYXzxcWvVAD28aTQXnwC1wFHQrHq4qNQPvwJhwPR38APV/z6hFncF4cBEcd2NR88A90D5crwRvzHW1awV46s0kzQcPwDbwTZID6QC+gMnGY9IvwCLjVauagOdgpvNL6pMkB8Ibcbv1d/4lcN551ag9YIE3sygtEO4eBtLV+SxUH0XfQLVqjhR29jA7kEVpgdBjIB2dfyT4PZ0ftVM0sLi7FoJ94L5oTaL4yZ4Gj8Fe0DT4DcAd8B28Bq3AWnBK9PTgP9ccbAUXRAv9kl9/WdAQsAnUBHj0lqW0QLhgUiCHgt/X+VEDwTrROdfA4OCPDt4ZMCN4PB6/glnhmjWqRvST/CB6qsX1Gcx7cBYMCt5E0Xv2CdfsOV4GL1L2550WCB88KZCDwe/tfKsJonOWGo9Fmh53hhV3iff4hjl3qPGmBG+x8bokeBWLgZzwJnRAdDG+RSt2gfTbON9qnOgc7oqotsFbbTyKpx37HKuNonNbGC/uhhHG48vywVestEA2iy7mmzbOpV9bs8PGiHNGGS8Gssp4FAPx2zp+crZwx0CGGy8Gssx4FYuBnPSmFLo81gSrG+Cm87xivcgaCOuVFetFOYEsN17FYiCs4l6s8Cxs04zXSLQ1LnW+x08mayDslq3iJ5M1EHak/0SNRbvRy6K/abzY2vNo43FIzQZ3pXQPwt8/fNBJxusevA3G45rPRNew2i06t53x4o4da7xewVtjvL8Sz/PbomHwhoQPxjdlCxk1EqwXLbJbQOvi4T+0XfQo5T15f54Yc8Hb4JHroifIE+M9BANEw4neK9EgdknhWT+Lhsqehrs1zr0iuXLlypUrV65c/5F+An6exvBqTn9jAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAXCAYAAADk3wSdAAABOklEQVR4Xu2UvytFYRjHHz8Gg4G6DMpsNiCDgQ1JKestZimJsNzBSlhkUsqkLBaKIoPBRHFL3b+AAZOy8Hl7nnO9nnSu407kU5865/k+vb3nvM85Iv/8KqbxBt/MezzBZst7sBjlVzhkWSqN+Ip3Poi4wHFfTGNEdBcrPjAasIQ1PkhjTXTRAR8Y4XE3fbES1/iIdT4wVnHUF9NoEd3lgQ8iwuGE9/5tJkQXnfWB0S56SJnYE1200wfGJBZ8sRK3+IS1PjDORHebiWPRgf+KOVx0tQ7cxW2cwnk8xa64KQx0ePyxqNaE67gc1RIWsA1fsNtqGzhT7jD6cV/0/R7hIfZ96vigVXS8Qk/CudWqIsztkl3n8Fl05JL/xY+4xF67zuOO6Nc4WO7ISPjqHrDe7odFD2pLMv4b/iDv7Q428mfd7zcAAAAASUVORK5CYII=>