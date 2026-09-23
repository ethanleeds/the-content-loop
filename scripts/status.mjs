#!/usr/bin/env node
// Mark a video approved, in progress, done or rejected.
// Usage: node scripts/status.mjs "<video title> | <status> | <why>"
// Rejected requires a why. The agent applies it to the queue note on its next run.
import fs from "node:fs";
import path from "node:path";

const OK = ["approved", "in progress", "done", "rejected"];
const file = path.join(process.cwd(), "vault", "Feedback-Log.md");
const [video = "", status = "", why = ""] = process.argv.slice(2).join(" ").split("|").map((s) => s.trim());
const st = status.toLowerCase();
if (!video || !OK.includes(st)) {
  console.error('usage: node scripts/status.mjs "<video> | approved|in progress|done|rejected | <why>"');
  process.exit(1);
}
if (st === "rejected" && !why) { console.error("a rejection needs a why. That's how the agent learns."); process.exit(1); }
if (!fs.existsSync(file)) { console.error("vault/Feedback-Log.md not found. Run from the repo root."); process.exit(1); }
const row = `| ${new Date().toISOString().slice(0, 10)} | ${video.replace(/\|/g, "/")} | ${st} | ${why.replace(/\|/g, "/")} |`;
const text = fs.readFileSync(file, "utf8");
const marker = "|---|---|---|---|";
const i = text.indexOf(marker);
if (i < 0) { console.error("could not find the log table"); process.exit(1); }
// insert after the last existing row of the log table
let end = text.indexOf("\n", i) + 1;
while (text.slice(end).startsWith("|")) end = text.indexOf("\n", end) + 1 || text.length;
fs.writeFileSync(file, text.slice(0, end) + row + "\n" + text.slice(end));
console.log("logged: " + row);
