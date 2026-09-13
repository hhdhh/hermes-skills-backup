/**
 * ljg-ppt-design Pi extension entry.
 *
 * Pi is the Pi Coding Agent. Extensions expose Python skills to Pi via a
 * TypeScript wrapper. This file wraps `~/.claude/skills/ljg-ppt-design/`
 * (the actual Python implementation).
 *
 * Security note: Uses `execFile` (not `exec`) to prevent shell injection.
 */

import { execFile, execFileSync } from "child_process";
import { existsSync, writeFileSync, mkdtempSync } from "fs";
import { tmpdir, homedir } from "os";
import { join } from "path";

const SKILL_PATH = join(homedir(), ".claude/skills/ljg-ppt-design");

function ensureInstalled(): void {
  if (!existsSync(join(SKILL_PATH, "__init__.py"))) {
    throw new Error(
      `ljg-ppt-design not found at ${SKILL_PATH}. ` +
        `Install: pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=ljg-ppt-design`
    );
  }
}

function runPython(args: string[]): string {
  ensureInstalled();
  const code =
    `import sys; sys.path.insert(0, ${JSON.stringify(SKILL_PATH)}); ` +
    `from ljg_ppt_design import ${args[0]}; ` +
    `import json; print(json.dumps(${args[0]}(), ensure_ascii=False))`;
  const out = execFileSync("python3", ["-c", code], { encoding: "utf-8" });
  return out.trim();
}

export const metadata = {
  name: "ljg-ppt-design",
  version: "0.1.0",
  description:
    "PPT design system — 4 presets × 12 layouts × 4 talk types × 5-dim review. " +
    "Lighter than cli-anything-libreoffice with built-in design intelligence.",
};

export function listPresets(): string {
  return runPython(["list_presets"]);
}

export function listTalkTypes(): string {
  return runPython(["list_talk_types"]);
}

export async function render(
  preset: string,
  talkType: string,
  contentJson: string,
  outputPath: string
): Promise<string> {
  ensureInstalled();
  // 用临时文件传 content(避免把 JSON 拼到命令行,既安全也避开长度限制)
  const tmpDir = mkdtempSync(join(tmpdir(), "ljg-ppt-"));
  const tmp = join(tmpDir, "content.json");
  writeFileSync(tmp, contentJson, "utf-8");

  await new Promise<void>((resolve, reject) => {
    execFile(
      "python3",
      ["-m", "ljg_ppt_design.cli", "render",
       "-p", preset, "-t", talkType, "-i", tmp, "-o", outputPath],
      { encoding: "utf-8" },
      (err, _stdout, stderr) => {
        if (err) reject(new Error(`render failed: ${stderr}`));
        else resolve();
      }
    );
  });
  return outputPath;
}

export default { metadata, listPresets, listTalkTypes, render };
