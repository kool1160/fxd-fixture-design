#!/usr/bin/env node

// Compatibility entrypoint: milestone selection now comes only from the registry.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function fail(message) {
  console.error(`FXD milestone registry error: ${message}`);
  process.exit(1);
}

function parseArgs(argv) {
  const args = {
    command: 'select',
    registry: 'docs/MILESTONE_STATE.json',
    number: '',
    context: '',
  };
  const rest = [...argv];
  if (rest[0] && !rest[0].startsWith('--')) args.command = rest.shift();
  while (rest.length) {
    const key = rest.shift();
    const value = rest.shift();
    if (!key?.startsWith('--') || value === undefined) fail(`invalid argument near ${key ?? '<end>'}`);
    if (key === '--registry') args.registry = value;
    else if (key === '--backlog') {
      if (value !== 'BACKLOG.md') fail('--backlog is retired; use --registry docs/MILESTONE_STATE.json');
      console.error('Warning: --backlog is retired; selecting from docs/MILESTONE_STATE.json.');
    } else if (key === '--number') args.number = value;
    else if (key === '--context') args.context = value;
    else fail(`unknown option ${key}`);
  }
  return args;
}

function readRegistry(registryPath) {
  if (!fs.existsSync(registryPath)) fail(`${registryPath} does not exist`);
  let registry;
  try {
    registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
  } catch (error) {
    fail(`cannot parse ${registryPath}: ${error.message}`);
  }
  return registry;
}

function runAuthoritativeValidation(registryPath) {
  const validator = path.join(repoRoot, 'scripts', 'validate_milestones.py');
  const candidates = process.platform === 'win32'
    ? [['py', ['-3']], ['python', []]]
    : [['python', []], ['python3', []]];
  for (const [command, prefix] of candidates) {
    const result = spawnSync(
      command,
      [...prefix, validator, '--repo-root', repoRoot, '--registry', registryPath],
      { cwd: repoRoot, encoding: 'utf8' },
    );
    if (result.error?.code === 'ENOENT') continue;
    if (result.status !== 0) {
      if (result.stdout?.trim()) console.error(result.stdout.trim());
      if (result.stderr?.trim()) console.error(result.stderr.trim());
      fail('authoritative Python governance validation failed; milestone selection did not run');
    }
    if (result.stdout?.trim()) console.log(result.stdout.trim());
    return;
  }
  fail('authoritative Python governance validator could not start');
}

function slugify(value) {
  return value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'milestone';
}

function writeOutput(name, value) {
  const outputPath = process.env.GITHUB_OUTPUT;
  if (!outputPath) return;
  const delimiter = `FXD_${name.toUpperCase()}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  fs.appendFileSync(outputPath, `${name}<<${delimiter}\n${String(value)}\n${delimiter}\n`);
}

const args = parseArgs(process.argv.slice(2));
const registryPath = path.resolve(repoRoot, args.registry);
runAuthoritativeValidation(registryPath);
const registry = readRegistry(registryPath);

if (args.command === 'validate') {
  const lane = registry.product_lane.paused ? 'paused' : `Active milestone ${registry.product_lane.active_milestone}`;
  console.log(`Validated ${registry.milestones.length} FXD milestones; product lane: ${lane}.`);
  process.exit(0);
}
if (args.command !== 'select') fail(`unknown command ${args.command}`);
if (registry.product_lane.paused) fail('the product lane is formally paused; no milestone may be selected');

const selected = registry.milestones.find((milestone) => milestone.status === 'Active');
if (!selected) fail('no Active milestone is registered');
if (!Number.isInteger(selected.issue) || selected.issue < 1) fail(`Active Milestone ${selected.number} has no authoritative issue`);
if (!Array.isArray(selected.implementation_prs) || !selected.implementation_prs.length) {
  fail(`Active Milestone ${selected.number} has no implementation PR`);
}
if (args.number.trim()) {
  const requested = Number(args.number);
  if (!Number.isInteger(requested) || requested < 1) fail(`invalid milestone number: ${args.number}`);
  if (requested !== selected.number) {
    fail(`Milestone ${requested} is not Active; registry authorizes only Milestone ${selected.number}`);
  }
}

const context = [
  '# Selected FXD Milestone',
  '',
  '> Current status is authoritative only in `docs/MILESTONE_STATE.json` and the linked GitHub issue.',
  '',
  `- Number: ${selected.number}`,
  `- Name: ${selected.title}`,
  `- Status: ${selected.status}`,
  `- Authoritative issue: #${selected.issue}`,
  `- Implementation PRs: ${selected.implementation_prs.map((number) => `#${number}`).join(', ')}`,
  `- Required evidence profiles: ${selected.evidence_profiles.join(', ')}`,
  '',
  '## Registry record',
  '',
  '```json',
  JSON.stringify(selected, null, 2),
  '```',
  '',
  'The workflow must append the complete authoritative issue body before invoking Codex.',
  '',
].join('\n');

if (args.context) {
  const contextPath = path.resolve(args.context);
  fs.mkdirSync(path.dirname(contextPath), { recursive: true });
  fs.writeFileSync(contextPath, context);
}

const slug = slugify(selected.title);
writeOutput('number', selected.number);
writeOutput('title', selected.title);
writeOutput('slug', slug);
writeOutput('status', selected.status);
writeOutput('issue_number', selected.issue);
writeOutput('evidence_profiles', selected.evidence_profiles.join(','));
writeOutput('recommended_level', selected.evidence_profiles.some((profile) => ['B', 'C', 'D', 'E'].includes(profile)) ? 'Sol' : 'Terra');
writeOutput('branch', `codex/milestone-${selected.number}-${slug}`);
console.log(`Selected Active Milestone ${selected.number}: ${selected.title} (Issue #${selected.issue})`);
