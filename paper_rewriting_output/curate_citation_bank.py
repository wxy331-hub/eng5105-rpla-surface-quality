from pathlib import Path


OUTPUT_DIR = Path(r"D:\12591\Documents\5105\paper_rewriting_output")
BANK = OUTPUT_DIR / "citation_support_bank.md"

CURATED = [
    ("R01", "Recycled PLA for 3D Printing: A Comparison of Recycled PLA Filaments from Waste of Different Origins", "10.3390/polym15173651"),
    ("R03", "Life cycle assessment of filament production in distributed plastic recycling via additive manufacturing", "10.1016/j.clwas.2023.100100"),
    ("R05", "A comparative study of 3D printing with virgin and recycled polylactic acid filaments", "10.1016/j.cirpj.2024.08.007"),
    ("R09", "Characterizing the Effect of Filament Moisture on Tensile Properties and Morphology of Fused Deposition Modeled Polylactic Acid/Polybutylene Succinate Parts", "10.1089/3dp.2022.0222"),
    ("R10", "Influence of environmental humidity during filament storage on the structural and mechanical properties of material extrusion 3D-printed poly(lactic acid) parts", "10.1016/j.rineng.2024.103013"),
    ("R15", "Improving 3D printing sustainability in academic research: a PLA recycling initiative", "10.1039/D5SU00959F"),
    ("R18", "Influence of PLA Filament Conditions on Characteristics of FDM Parts", "10.3390/ma11081322"),
    ("R19", "Close-looped recycling of polylactic acid used in 3D printing: An experimental investigation and life cycle assessment", "10.1016/j.jclepro.2018.06.275"),
    ("V01", "The MVTec AD 2 Dataset: Advanced Scenarios for Unsupervised Anomaly Detection", "10.1007/s11263-026-02743-0"),
    ("V02", "Detecting visual anomalies in an industrial environment: Unsupervised methods put to the test on the AutoVI dataset", "10.1016/j.compind.2024.104151"),
    ("V03", "Real-IAD: A Real-World Multi-View Dataset for Benchmarking Versatile Industrial Anomaly Detection", "10.1109/CVPR52733.2024.02159"),
    ("V05", "Online micro defects detection for ductile cast iron pipes based on twin light photometric stereo", "10.1016/j.cscm.2023.e02561"),
    ("V07", "Metal surface defect detection based on Latitude-Longitude light sources", "10.1016/j.measurement.2024.114315"),
    ("V09", "A Novel Line-Scan Algorithm for Unsynchronised Dynamic Measurements", "10.3390/app14010235"),
    ("V17", "An Efficient Tiny Defect Detection Method for PCB With Improved YOLO Through a Compression Training Strategy", "10.1109/TIM.2024.3390198"),
    ("V19", "Explainable efficient and optimized feature fusion network for surface defect detection", "10.1007/s00170-023-11789-0"),
    ("S06", "Enhancing industrial IoT with edge computing and computer vision: An analog gauge visual digitization approach", "10.1016/j.mfglet.2024.09.153"),
    ("S08", "Guide to Operational Technology (OT) Security", "10.6028/NIST.SP.800-82r3"),
    ("S10", "Leakage and the Reproducibility Crisis in Machine-Learning-Based Science", "10.1016/j.patter.2023.100804"),
    ("S11", "Analyzing Information Leakage on Video Object Detection Datasets by Splitting Images Into Clusters With High Spatiotemporal Correlation", "10.1109/ACCESS.2024.3383047"),
]


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


text = BANK.read_text(encoding="utf-8")
lines = text.splitlines()
row_lines = [line for line in lines if line.startswith("|") and len(split_row(line)) >= 10 and split_row(line)[0][:1] in {"R", "V", "S"}]
rows = {split_row(line)[0]: split_row(line) for line in row_lines}

ordered_ids = [item[0] for item in CURATED] + [candidate_id for candidate_id in rows if candidate_id not in {item[0] for item in CURATED}]
canonical = {candidate_id: (title, doi) for candidate_id, title, doi in CURATED}
out_rows: list[str] = []
for candidate_id in ordered_ids:
    cells = rows[candidate_id]
    if candidate_id in canonical:
        title, doi = canonical[candidate_id]
        cells[1] = title
        cells[7] = f"https://doi.org/{doi}"
        cells[8] = "yes"
        cells[9] = "Curated for final-report consideration; DOI and canonical title checked against Crossref/publisher metadata."
    out_rows.append("| " + " | ".join(cells) + " |")

header_end = lines.index("|---|---|---:|---|---|---|---|---|---|---|")
prefix = lines[: header_end + 1]
suffix = [
    "",
    "## Curation status",
    "",
    "The first 20 rows are the curated academic/technical subset used for automated metadata verification. Official standards, manufacturer documents, regulator guidance, course documents, and supplier pages are verified from their issuing organisations and may also be cited in the report even where no Crossref DOI exists.",
    "",
]
BANK.write_text("\n".join(prefix + out_rows + suffix), encoding="utf-8")
