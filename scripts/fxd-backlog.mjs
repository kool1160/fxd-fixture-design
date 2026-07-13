#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

function fail(message) {
  console.error(`FXD backlog error: ${message}`);
  process.exit(1);
}

function parseArgs(argv) {
  const args = { command: 'select', backlog: 'BACKLOG.md', number: '', context: '' };
  const rest = [...argv];
  if (rest[0] && !rest[0].startsWith('--')) args.command = rest.shift();
  while (rest.length) {
    const key = rest.shift();
    const value = rest.shift();
    if (!key?.startsWith('--') || value === undefined) fail(`invalid argument near ${key ?? '<end>'}`);
    if (key === '--backlog') args.backlog = value;
    else if (key === '--number') args.number = value;
    else if (key === '--context') args.context = value;
    else fail(`unknown option ${key}`);
  }
  return args;
}

function parseMilestones(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const milestones = [];
  const heading = /^## Milestone\s+(\d+)\s+—\s+(.+?)\s*$/;

  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(heading);
    if (!match) continue;

    const start = index;
    let end = lines.length;
    for (let next = index + 1; next < lines.length; next += 1) {
      if (heading.test(lines[next]) || /^## Deprioritized\b/.test(lines[next])) {
        end = next;
        break;
      }
    }

    const blockLines = lines.slice(start, end);
    const statusLine = blockLines.find((line) => /^\*\*Status:\*\*/.test(line));
    const levelLine = blockLines.find((line) => /^\*\*Recommended level:\*\*/.test(line));
    if (!statusLine) fail(`Milestone ${match[1]} has no Status line`);
    if (!levelLine) fail(`Milestone ${match[1]} has no Recommended level line`);

    milestones.push({
      number: Number(match[1]),
      title: match[2].trim(),
      status: statusLine.replace(/^\*\*Status:\*\*\s*/, '').trim(),
      recommendedLevel: levelLine.replace(/^\*\*Recommended level:\*\*\s*/, '').trim(),
      markdown: blockLines.join('\n').trim(),
    });
    index = end - 1;
  }

  if (!milestones.length) fail('no milestone headings were found');
  return milestones;
}

function isComplete(status) {
  return /^complete\b/i.test(status);
}

function isBlocked(status) {
  return /^(blocked|paused|waiting)\b/i.test(status);
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
const backlogPath = path.resolve(args.backlog);
if (!fs.existsSync(backlogPath)) fail(`${args.backlog} does not exist`);
const milestones = parseMilestones(fs.readFileSync(backlogPath, 'utf8'));

if (args.command === 'validate') {
  const numbers = new Set();
  for (const milestone of milestones) {
    if (numbers.has(milestone.number)) fail(`duplicate Milestone ${milestone.number}`);
    numbers.add(milestone.number);
  }
  console.log(`Validated ${milestones.length} FXD milestones.`);
  process.exit(0);
}

if (args.command !== 'select') fail(`unknown command ${args.command}`);

let selected;
if (args.number.trim()) {
  const requested = Number(args.number);
  if (!Number.isInteger(requested) || requested < 1) fail(`invalid milestone number: ${args.number}`);
  selected = milestones.find((milestone) => milestone.number === requested);
  if (!selected) fail(`Milestone ${requested} was not found`);
  if (isComplete(selected.status)) fail(`Milestone ${requested} is already complete`);
} else {
  selected = milestones.find((milestone) => !isComplete(milestone.status) && !isBlocked(milestone.status));
  if (!selected) fail('all remaining milestones are complete or blocked');
}

const context = [
  '# Selected FXD Milestone',
  '',
  `- Number: ${selected.number}`,
  `- Name: ${selected.title}`,
  `- Current status: ${selected.status}`,
  `- Recommended level: ${selected.recommendedLevel}`,
  '',
  '## Authoritative backlog excerpt',
  '',
  selected.markdown,
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
writeOutput('recommended_level', selected.recommendedLevel);
writeOutput('branch', `codex/milestone-${selected.number}-${slug}`);
console.log(`Selected Milestone ${selected.number}: ${selected.title}`);
