/**
 * build-imports.js
 * Generates API-ready import files from source flow files.
 * Run: node scripts/build-imports.js
 *
 * Transforms applied to each flow:
 * - Keep only: name, nodes, connections, settings
 * - Replace em-dash (—) with --
 * - Strip Cyrillic comment lines from jsCode
 * - Remove empty credential IDs ("id": "")
 * - Add missing conditions.options to IF nodes (required by n8n typeVersion 2.2)
 */

const fs = require('fs');
const path = require('path');

const FLOWS = [
  { src: 'gmail-flow-api.json',        dst: 'gmail-flow-import.json' },
  { src: 'mailde-flow-api.json',       dst: 'mailde-flow-import.json' },
  { src: 'firecrawl-flow-api.json',    dst: 'firecrawl-flow-import.json' },
  { src: 'manual-flow-api.json',       dst: 'manual-flow-import.json' },
  { src: 'job-apis-flow-api.json',     dst: 'job-apis-flow-import.json' },
  { src: 'daily-digest-flow-api.json', dst: 'daily-digest-flow-import.json' },
];

const N8N_DIR = path.join(__dirname, '../n8n');

const IF_OPTIONS = { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 };

function processNode(n) {
  // Strip Cyrillic comment lines from jsCode
  if (n.parameters && n.parameters.jsCode) {
    n.parameters.jsCode = n.parameters.jsCode
      .split('\n')
      .filter(line => !/[Ѐ-ӿ]/.test(line))
      .join('\n');
  }

  // Remove empty credential IDs
  if (n.credentials) {
    Object.keys(n.credentials).forEach(key => {
      if (n.credentials[key] && n.credentials[key].id === '') delete n.credentials[key];
    });
    if (Object.keys(n.credentials).length === 0) delete n.credentials;
  }

  // Fix IF nodes: add missing conditions.options
  if (n.type === 'n8n-nodes-base.if' && n.parameters && n.parameters.conditions && !n.parameters.conditions.options) {
    n.parameters.conditions.options = IF_OPTIONS;
  }

  return n;
}

let ok = 0;
let skip = 0;

FLOWS.forEach(({ src, dst }) => {
  const srcPath = path.join(N8N_DIR, src);
  const dstPath = path.join(N8N_DIR, dst);

  if (!fs.existsSync(srcPath)) {
    console.log(`SKIP (not found): ${src}`);
    skip++;
    return;
  }

  let raw = fs.readFileSync(srcPath, 'utf8');
  if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1); // strip BOM

  const f = JSON.parse(raw);

  const clean = {
    name: f.name.replace(/—/g, '--'),
    nodes: f.nodes.map(n => processNode(JSON.parse(JSON.stringify(n)))),
    connections: f.connections,
    settings: f.settings,
  };

  const json = JSON.stringify(clean, null, 2);

  // Validate
  JSON.parse(json);

  const cyrillic = (json.match(/[Ѐ-ӿ]/g) || []).length;
  const emptyIds = (json.match(/"id":\s*""/g) || []).length;

  if (cyrillic > 0) console.warn(`  WARNING: ${cyrillic} Cyrillic chars remain in ${dst}`);
  if (emptyIds > 0) console.warn(`  WARNING: ${emptyIds} empty credential IDs in ${dst}`);

  fs.writeFileSync(dstPath, json, 'utf8');
  console.log(`OK: ${src} -> ${dst}`);
  ok++;
});

console.log(`\nDone: ${ok} built, ${skip} skipped.`);
