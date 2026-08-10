import { describe, expect, it } from "vitest";

import { classifySseResultStatus, nextSseRecoveryDelay } from "./sseRecovery";

describe("SSE recovery policy", () => {
  it("uses bounded reconnection delays", () => {
    expect(nextSseRecoveryDelay(0)).toBe(1000);
    expect(nextSseRecoveryDelay(1)).toBe(3000);
    expect(nextSseRecoveryDelay(2)).toBeNull();
  });

  it("treats an unfinished result as recoverable", () => {
    expect(classifySseResultStatus(200)).toBe("completed");
    expect(classifySseResultStatus(409)).toBe("running");
    expect(classifySseResultStatus(500)).toBe("failed");
  });
});
