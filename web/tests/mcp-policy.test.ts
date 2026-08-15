import test from "node:test";
import assert from "node:assert/strict";

import {
  isHighRiskMcpChange,
  type McpServerConfig,
} from "../lib/mcp-api";

function server(overrides: Partial<McpServerConfig> = {}): McpServerConfig {
  return {
    type: "stdio",
    command: "echo",
    args: [],
    env: {},
    cwd: "",
    url: "",
    headers: {},
    tool_timeout: 30,
    enabled_tools: ["*"],
    enabled: true,
    ...overrides,
  };
}

test("adding a server is high-risk", () => {
  assert.equal(isHighRiskMcpChange({}, { "new-server": server() }), true);
});

test("enabling a previously-disabled server is high-risk", () => {
  const before = { srv: server({ enabled: false }) };
  const after = { srv: server({ enabled: true }) };
  assert.equal(isHighRiskMcpChange(before, after), true);
});

test("disabling a server or editing a disabled one is not high-risk", () => {
  const before = { srv: server({ enabled: true }) };
  const after = { srv: server({ enabled: false }) };
  assert.equal(isHighRiskMcpChange(before, after), false);
});

test("no-op changes are not high-risk", () => {
  const before = { srv: server() };
  const after = { srv: server() };
  assert.equal(isHighRiskMcpChange(before, after), false);
});

test("empty-to-empty is not high-risk", () => {
  assert.equal(isHighRiskMcpChange({}, {}), false);
});
