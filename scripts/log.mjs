#!/usr/bin/env node
// Append a row to vault/Loop-Ledger.md.
// Usage: node scripts/log.mjs "subject | guess | actual | correction"
// Post with guess filled and actual blank; the weekly loop fills actual in.
import fs from "node:fs";
import path from "node:path";

const ledger = path.join(process.cwd(), "vault", "Loop-Ledger.md");
const arg = process.argv.slice(2).join(" ").trim();
if (!arg) {
  console.error('usage: node scripts/log.mjs "subject | guess | actual | correction"');
  process.exit(1);
}
const cells = arg.split("|").map((c) => c.trim().replace(/\|/g, "/"));
while (cells.length < 4) cells.push("");
const [subject, guess, actual, correction] = cells;
if (!subject) { console.error("subject is required"); process.exit(1); }
if (!guess) console.warn("no guess: this row is a log, not a lesson");
const date = new Date().toISOString().slice(0, 10);
const row = `| ${date} | ${subject} | ${guess} | ${actual} | ${correction} |\n`;
if (!fs.existsSync(ledger)) { console.error("vault/Loop-Ledger.md not found. Run from the repo root."); process.exit(1); }
const text = fs.readFileSync(ledger, "utf8");
fs.writeFileSync(ledger, text.endsWith("\n") ? text + row : text + "\n" + row);
console.log("logged: " + row.trim());
