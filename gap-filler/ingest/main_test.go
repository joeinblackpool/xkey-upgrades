package main

import (
	"encoding/json"
	"testing"
)

// Shape copied from GitHub's releases API: nested author object must not break decoding.
const sample = `[
 {"tag_name":"v15.1.0","name":"15.1.0","body":"## Changes\n- Added foo\n- **Breaking:** removed legacy router\n- Renamed config key x to y","html_url":"https://github.com/o/r/releases/tag/v15.1.0","draft":false,"prerelease":false,"published_at":"2026-10-01T00:00:00Z","author":{"login":"bot","id":1}},
 {"tag_name":"v15.1.0-canary.1","draft":false,"prerelease":true,"published_at":"2026-09-20T00:00:00Z","author":{"login":"bot"}},
 {"tag_name":"v15.0.3","draft":false,"prerelease":false,"published_at":"2026-09-10T00:00:00Z","author":{"login":"bot"}}
]`

func TestDecodeAndBuild(t *testing.T) {
	var rels []Release
	if err := json.Unmarshal([]byte(sample), &rels); err != nil {
		t.Fatal(err)
	}
	rec, ok := buildRecord(opportunity{Project: "X", Release: "v15.1.0"}, "o/r", rels)
	if !ok {
		t.Fatal("release not found")
	}
	if rec.PreviousTag != "v15.0.3" {
		t.Errorf("previous tag = %q, want v15.0.3 (skipping prerelease)", rec.PreviousTag)
	}
	if len(rec.BreakingLines) != 2 {
		t.Errorf("breaking lines = %v, want 2", rec.BreakingLines)
	}
}

func TestMissingRelease(t *testing.T) {
	if _, ok := buildRecord(opportunity{Release: "v9"}, "o/r", nil); ok {
		t.Error("expected not found")
	}
}
