/**
 * Football Predictor Bridge
 * Integrates the football prediction engine with Pi Web UI
 */
import { spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PREDICTOR_DIR = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor";
const PYTHON = "C:/Python314/python.exe";

/**
 * Analyze a match using the football predictor
 */
export async function analyzeMatch(homeTeam, awayTeam, options = {}) {
  return new Promise((resolve, reject) => {
    const args = [
      join(PREDICTOR_DIR, "direct_predictor.py"),
      "--home", homeTeam,
      "--away", awayTeam,
    ];
    
    if (options.date) args.push("--date", options.date);
    if (options.competition) args.push("--competition", options.competition);
    if (options.neutralVenue) args.push("--neutral-venue");
    
    const proc = spawn(PYTHON, args, {
      cwd: PREDICTOR_DIR,
      timeout: 30000,
    });
    
    let output = "";
    proc.stdout.on("data", (data) => { output += data.toString(); });
    proc.stderr.on("data", (data) => { /* ignore stderr */ });
    
    proc.on("close", (code) => {
      if (code === 0) {
        try {
          resolve(JSON.parse(output));
        } catch {
          resolve({ error: "Parse error", raw: output });
        }
      } else {
        reject(new Error(`Process exited with code ${code}`));
      }
    });
    
    proc.on("error", reject);
  });
}

/**
 * Get all World Cup 2026 fixtures with predictions
 */
export async function getWcFixtures() {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [
      join(PREDICTOR_DIR, "wc2026_predictor.py"),
      "--json"
    ], {
      cwd: PREDICTOR_DIR,
      timeout: 30000,
    });
    
    let output = "";
    proc.stdout.on("data", (data) => { output += data.toString(); });
    
    proc.on("close", (code) => {
      if (code === 0) {
        try { resolve(JSON.parse(output)); }
        catch { resolve({ error: "Parse error" }); }
      } else {
        reject(new Error(`Exit code ${code}`));
      }
    });
    
    proc.on("error", reject);
  });
}

/**
 * Get today's best matches
 */
export async function getBestMatches() {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [
      "-c", `
import sys, json
sys.path.insert(0, r"${PREDICTOR_DIR.replace(/\\/g, '\\\\')}")
from prediction_engine import get_daily_matches, rate_matches
matches = get_daily_matches()
if matches:
    best = rate_matches(matches)
    print(json.dumps(best[:10], default=str))
else:
    print(json.dumps([]))
`
    ], {
      cwd: PREDICTOR_DIR,
      timeout: 60000,
    });
    
    let output = "";
    proc.stdout.on("data", (data) => { output += data.toString(); });
    
    proc.on("close", (code) => {
      if (code === 0) {
        try { resolve(JSON.parse(output)); }
        catch { resolve([]); }
      } else {
        resolve([]);
      }
    });
    
    proc.on("error", () => resolve([]));
  });
}
