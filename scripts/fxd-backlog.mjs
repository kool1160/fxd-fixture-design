#!/usr/bin/env node

// Historical-registry validation compatibility entrypoint.
//
// Issue #66 permanently retired automatic work selection. No missing file,
// checkout shape, environment variable, or legacy registry may re-enable it.
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
    if (!key?.startsWith('--') || value === undefined) {
      fail(`invalid argument near ${key ?? '<end>'}`);
    }
    if (key === '--registry') args.registry = value;
    else if (key === '--backlog') {
      if (value !== 'BACKLOG.md') {
        fail('--backlog is retired; use --registry docs/MILESTONE_STATE.json');
      }
      console.error('Warning: --backlog is retired; validating docs/MILESTONE_STATE.json.');
    } else if (key === '--number') args.number = value;
    else if (key === '--context') args.context = value;
    else fail(`unknown option ${key}`);
  }
  return args;
}

function readRegistry(registryPath) {
  if (!fs.existsSync(registryPath)) fail(`${registryPath} does not exist`);
  try {
    return JSON.parse(fs.readFileSync(registryPath, 'utf8'));
  } catch (error) {
    fail(`cannot parse ${registryPath}: ${error.message}`);
  }
}

function runHistoricalValidation(registryPath) {
  const validator = path.join(repoRoot, 'scripts', 'validate_legacy_milestones.py');
  const candidates = process.platform === 'win32'
    ? [['py', ['-3']], ['python', []]]
    : [['python', []], ['python3', []]];
  for (const [command, prefix] of candidates) {
    const result = spawnSync(
      command,
      [
        ...prefix,
        validator,
        '--repo-root',
        repoRoot,
        '--registry',
        registryPath,
      ],
      { cwd: repoRoot, encoding: 'utf8' },
    );
    if (result.error?.code === 'ENOENT') continue;
    if (result.status !== 0) {
      if (result.stdout?.trim()) console.error(result.stdout.trim());
      if (result.stderr?.trim()) console.error(result.stderr.trim());
      fail('historical Python governance validation failed');
    }
    if (result.stdout?.trim()) console.log(result.stdout.trim());
    return;
  }
  fail('historical Python governance validator could not start');
}

const args = parseArgs(process.argv.slice(2));
const registryPath = path.resolve(repoRoot, args.registry);
runHistoricalValidation(registryPath);
const registry = readRegistry(registryPath);

if (args.command === 'validate') {
  const projection = registry.product_lane.paused
    ? 'pre-reset lane pause recorded'
    : `pre-reset milestone marker ${registry.product_lane.active_milestone} recorded`;
  console.log(
    `Validated ${registry.milestones.length} historical FXD milestone records; `
    + `frozen historical projection only: ${projection}.`,
  );
  process.exit(0);
}
if (args.command !== 'select') fail(`unknown command ${args.command}`);

// Intentionally unconditional: a missing protocol/control file must not turn
// the superseded selector back into executable project authority.
fail(
  'automatic milestone selection is retired by Issue #66; read docs/CONTROL_STATE.json, CURRENT.md, and docs/OPERATOR_PROTOCOL.md, then let Review-Control issue CONTINUE',
);
