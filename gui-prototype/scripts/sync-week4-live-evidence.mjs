import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const guiRoot = resolve(scriptDir, "..");
const evidenceRoot = resolve(guiRoot, "..", "data", "output", "week4_live");
const targetRoot = join(guiRoot, "public", "live-evidence");
const files = ["summary.json", "detections.json", "annotated_frame.jpg", "raw_frame.jpg"];

await mkdir(targetRoot, { recursive: true });
await Promise.all(files.map((file) => copyFile(join(evidenceRoot, file), join(targetRoot, file))));
console.log(`Synced ${files.length} live evidence files to ${targetRoot}`);
