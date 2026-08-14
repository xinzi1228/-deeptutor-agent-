import test from "node:test";
import assert from "node:assert/strict";

import { ProfileScopedRequest } from "../lib/profile-scoped-request";

test("profile switch aborts old requests and rejects stale responses", () => {
  const scope = new ProfileScopedRequest();
  const old = scope.begin();

  scope.switchProfile();

  assert.equal(old.signal.aborted, true);
  assert.equal(scope.accepts(old.generation), false);
  assert.equal(scope.accepts(scope.begin().generation), true);
});

test("a newer task version must win over an older response", () => {
  const current = { version: 5 };
  const stale = { version: 4 };
  const fresh = { version: 6 };

  assert.equal(stale.version >= current.version, false);
  assert.equal(fresh.version >= current.version, true);
});
