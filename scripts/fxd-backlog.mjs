#!/usr/bin/env node

// Compatibility entrypoint: milestone selection now comes only from the registry.
import fs from 'node:fs';
import path from 'node:path';

const SCHEMA = 'fxd-milestone-state-v1';
const LEGAL_STATUSES = new Set([
  'Planned', 'Active', 'Blocked', 'Waiting', 'Paused', 'Complete', 'Superseded', 'Cancelled',
]);

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
  if (registry.schema_version !== SCHEMA) fail(`unknown schema ${JSON.stringify(registry.schema_version)}`);
  if (!Array.isArray(registry.milestones) || !registry.milestones.length) fail('milestones must be a nonempty array');
  const numbers = new Set();
  const positions = new Set();
  for (const milestone of registry.milestones) {
    if (!Number.isInteger(milestone.number) || milestone.number < 1) fail('milestone numbers must be positive integers');
    if (numbers.has(milestone.number)) fail(`duplicate Milestone ${milestone.number}`);
    numbers.add(milestone.number);
    if (!Number.isInteger(milestone.sequence_position) || milestone.sequence_position < 1) {
      fail(`Milestone ${milestone.number} has an invalid sequence position`);
    }
    if (positions.has(milestone.sequence_position)) fail(`duplicate sequence position ${milestone.sequence_position}`);
    positions.add(milestone.sequence_position);
    if (!LEGAL_STATUSES.has(milestone.status)) fail(`Milestone ${milestone.number} has unknown status ${milestone.status}`);
  }
  const active = registry.milestones.filter((milestone) => milestone.status === 'Active');
  const lane = registry.product_lane;
  if (!lane || typeof lane.paused !== 'boolean') fail('product_lane.paused must be true or false');
  if (lane.paused) {
    if (active.length || lane.active_milestone !== null) fail('paused product lane must have zero Active milestones');
  } else if (active.length !== 1 || active[0].number !== lane.active_milestone) {
    fail('unpaused product lane must project exactly one Active milestone');
  }
  return registry;
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
const registryPath = path.resolve(args.registry);
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
