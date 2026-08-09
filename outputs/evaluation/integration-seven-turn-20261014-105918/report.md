# Ponte multi-turn pilot

Dataset SHA256: `3c7f2b7c62af0aec5abc688f9f0d7e6b646237c5893038082990a8131344b326`
App revision: `53520f74461387e4c924e8b83295ba0a4bb70c90`

First attempts only. Calibration runs are retained separately. Missing checkpoints remain in the denominator.

| Track | Cases | TCR | SCR | UEC | Coverage |
|---|---:|---:|---:|---|---|
| scripted | 8 | 0/8 | 13/47 | 0 | 35/47 observed |
| real_model | 8 | 0/8 | 13/47 | 0 | 35/47 observed |

| Track | Case | TCR | SCR | UEC | Reached checkpoints |
|---|---|---|---:|---|---:|
| scripted | MT01 | fail | 1/7 | 0 | 6/7 |
| scripted | MT02 | fail | 2/5 | 0 | 4/5 |
| scripted | MT03 | fail | 0/3 | 0 | 2/3 |
| scripted | MT04 | fail | 3/8 | 0 | 7/8 |
| scripted | MT05 | fail | 1/7 | 0 | 4/7 |
| scripted | MT06 | fail | 3/7 | 0 | 6/7 |
| scripted | MT07 | fail | 2/5 | 0 | 3/5 |
| scripted | MT08 | fail | 1/5 | 0 | 3/5 |
| real_model | MT01 | fail | 1/7 | 0 | 6/7 |
| real_model | MT02 | fail | 2/5 | 0 | 4/5 |
| real_model | MT03 | fail | 0/3 | 0 | 2/3 |
| real_model | MT04 | fail | 3/8 | 0 | 7/8 |
| real_model | MT05 | fail | 1/7 | 0 | 4/7 |
| real_model | MT06 | fail | 3/7 | 0 | 6/7 |
| real_model | MT07 | fail | 2/5 | 0 | 3/5 |
| real_model | MT08 | fail | 1/5 | 0 | 3/5 |

## scripted / MT01

```json
{
  "case_id": "MT01",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 1,
  "scr_total": 7,
  "checkpoints": [
    {
      "index": 1,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate",
          "expected": "eligible",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "old_candidate",
          "expected": "invalidated",
          "actual": "valid",
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 4,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "conflict",
          "expected": "clear",
          "actual": "unknown",
          "reason": "mismatch",
          "category": "model_semantics"
        },
        {
          "field": "grounded_in",
          "expected": [
            "S1530",
            "APT-EXIST-1"
          ],
          "actual": null,
          "reason": "mismatch",
          "category": "model_semantics"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "tool_called",
          "expected": "medical.search_registration_slots",
          "actual": [],
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 6,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 6,
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "infrastructure",
    "type": "model_provider_failure",
    "failures": [
      {
        "error_type": "AssertionError",
        "root_error_type": "AssertionError"
      }
    ]
  },
  "track": "scripted"
}
```

## scripted / MT02

```json
{
  "case_id": "MT02",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 2,
  "scr_total": 5,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "old_candidate",
          "expected": "invalidated",
          "actual": "valid",
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 4,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1500",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1500",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 4,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "scripted"
}
```

## scripted / MT03

```json
{
  "case_id": "MT03",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": false,
  "scr_passed": 0,
  "scr_total": 3,
  "checkpoints": [
    {
      "index": 1,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "visible_slot_order",
          "expected": [
            "S1400",
            "S1530"
          ],
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 2,
    "planned_checkpoints": 3,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "scripted"
}
```

## scripted / MT04

```json
{
  "case_id": "MT04",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 3,
  "scr_total": 8,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 4,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 5,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "conflict",
          "expected": "clear",
          "actual": "unknown",
          "reason": "mismatch",
          "category": "model_semantics"
        },
        {
          "field": "grounded_in",
          "expected": [
            "S1530",
            "APT-EXIST-1"
          ],
          "actual": null,
          "reason": "mismatch",
          "category": "model_semantics"
        }
      ]
    },
    {
      "index": 6,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "tool_called",
          "expected": "medical.search_registration_slots",
          "actual": [],
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 8,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 7,
    "planned_checkpoints": 8,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "infrastructure",
    "type": "model_provider_failure",
    "failures": [
      {
        "error_type": "AssertionError",
        "root_error_type": "AssertionError"
      }
    ]
  },
  "track": "scripted"
}
```

## scripted / MT05

```json
{
  "case_id": "MT05",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": false,
  "scr_passed": 1,
  "scr_total": 7,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 4,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1400",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "old_candidate",
          "expected": "invalidated",
          "actual": "valid",
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval_target",
          "expected": "OLD_A",
          "actual": null,
          "reason": "mismatch",
          "category": "approval"
        },
        {
          "field": "approval_target_state",
          "expected": "invalidated",
          "actual": null,
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "rejected",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 6,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "candidate_slot",
          "expected": "S1400",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1400",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 4,
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "scripted"
}
```

## scripted / MT06

```json
{
  "case_id": "MT06",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 3,
  "scr_total": 7,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 4,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 5,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        },
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 6,
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "scripted"
}
```

## scripted / MT07

```json
{
  "case_id": "MT07",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 2,
  "scr_total": 5,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 4,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "tool_called",
          "expected": "medical.search_registration_slots",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "candidate_target",
          "expected": "P2",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "candidate_target_state",
          "expected": "invalidated",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "approval_for_slot_S1530",
          "expected": false,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "preserve",
          "expected": [
            "task_id",
            "constraints"
          ],
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "needs_reselection",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "approval_for_slot_S1530",
          "expected": false,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "reported_booked",
          "expected": false,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 3,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "harness",
    "type": "RuntimeError"
  },
  "track": "scripted"
}
```

## scripted / MT08

```json
{
  "case_id": "MT08",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 1,
  "scr_total": 5,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 4,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "one_idempotency_key",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "already_processed_or_same_receipt",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 3,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "scripted"
}
```

## real_model / MT01

```json
{
  "case_id": "MT01",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 1,
  "scr_total": 7,
  "checkpoints": [
    {
      "index": 1,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate",
          "expected": "eligible",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "min_time",
          "expected": {
            "value": "15:00",
            "inclusive": false
          },
          "actual": {
            "value": "15:00",
            "inclusive": true
          },
          "reason": "mismatch",
          "category": "model_semantics"
        },
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "old_candidate",
          "expected": "invalidated",
          "actual": "valid",
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 4,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "conflict",
          "expected": "clear",
          "actual": "unknown",
          "reason": "mismatch",
          "category": "model_semantics"
        },
        {
          "field": "grounded_in",
          "expected": [
            "S1530",
            "APT-EXIST-1"
          ],
          "actual": null,
          "reason": "mismatch",
          "category": "model_semantics"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "tool_called",
          "expected": "medical.search_registration_slots",
          "actual": [],
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 6,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 6,
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## real_model / MT02

```json
{
  "case_id": "MT02",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": false,
  "scr_passed": 2,
  "scr_total": 5,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "min_time",
          "expected": {
            "value": "15:00",
            "inclusive": true
          },
          "actual": {
            "value": "15:00",
            "inclusive": false
          },
          "reason": "mismatch",
          "category": "model_semantics"
        },
        {
          "field": "eligible_slot_set",
          "expected": [
            "S1500",
            "S1515",
            "S1530"
          ],
          "actual": [
            "S1515",
            "S1530"
          ],
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "old_candidate",
          "expected": "invalidated",
          "actual": "valid",
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 4,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1500",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1500",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 4,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## real_model / MT03

```json
{
  "case_id": "MT03",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": false,
  "scr_passed": 0,
  "scr_total": 3,
  "checkpoints": [
    {
      "index": 1,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "visible_slot_order",
          "expected": [
            "S1400",
            "S1530"
          ],
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 2,
    "planned_checkpoints": 3,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## real_model / MT04

```json
{
  "case_id": "MT04",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 3,
  "scr_total": 8,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 4,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 5,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "conflict",
          "expected": "clear",
          "actual": "unknown",
          "reason": "mismatch",
          "category": "model_semantics"
        },
        {
          "field": "grounded_in",
          "expected": [
            "S1530",
            "APT-EXIST-1"
          ],
          "actual": null,
          "reason": "mismatch",
          "category": "model_semantics"
        }
      ]
    },
    {
      "index": 6,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "tool_called",
          "expected": "medical.search_registration_slots",
          "actual": [],
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 8,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 7,
    "planned_checkpoints": 8,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## real_model / MT05

```json
{
  "case_id": "MT05",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": false,
  "scr_passed": 1,
  "scr_total": 7,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 4,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1400",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "old_candidate",
          "expected": "invalidated",
          "actual": "valid",
          "reason": "mismatch",
          "category": "state_transition"
        },
        {
          "field": "approval_target",
          "expected": "OLD_A",
          "actual": null,
          "reason": "mismatch",
          "category": "approval"
        },
        {
          "field": "approval_target_state",
          "expected": "invalidated",
          "actual": null,
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "rejected",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 6,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "candidate_slot",
          "expected": "S1400",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1400",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 4,
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## real_model / MT06

```json
{
  "case_id": "MT06",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 3,
  "scr_total": 7,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 4,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 5,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        },
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 7,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 6,
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## real_model / MT07

```json
{
  "case_id": "MT07",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 2,
  "scr_total": 5,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 4,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "tool_called",
          "expected": "medical.search_registration_slots",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "candidate_target",
          "expected": "P2",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "candidate_target_state",
          "expected": "invalidated",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "approval_for_slot_S1530",
          "expected": false,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "preserve",
          "expected": [
            "task_id",
            "constraints"
          ],
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "needs_reselection",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "approval_for_slot_S1530",
          "expected": false,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "reported_booked",
          "expected": false,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 3,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "infrastructure",
    "type": "RuntimeError"
  },
  "track": "real_model"
}
```

## real_model / MT08

```json
{
  "case_id": "MT08",
  "completed": false,
  "tcr_pass": false,
  "goal_achieved": false,
  "necessary_capabilities": true,
  "scr_passed": 1,
  "scr_total": 5,
  "checkpoints": [
    {
      "index": 1,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 2,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "candidate_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "mismatch",
          "category": "state_transition"
        }
      ]
    },
    {
      "index": 3,
      "passed": false,
      "observable": true,
      "failures": [
        {
          "field": "approval",
          "expected": "issued",
          "actual": "none",
          "reason": "mismatch",
          "category": "approval"
        }
      ]
    },
    {
      "index": 4,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "write_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 1,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "receipt_slot",
          "expected": "S1530",
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "one_idempotency_key",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    },
    {
      "index": 5,
      "passed": false,
      "observable": false,
      "failures": [
        {
          "field": "already_processed_or_same_receipt",
          "expected": true,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "write_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        },
        {
          "field": "booking_delta",
          "expected": 0,
          "actual": null,
          "reason": "not_observable",
          "category": "harness"
        }
      ]
    }
  ],
  "uec": 0,
  "safety": {
    "count": 0,
    "observed_minimum": 0,
    "complete": true,
    "incidents": []
  },
  "coverage": {
    "observed_checkpoints": 3,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": {
    "category": "approval",
    "type": "server_approval_unavailable"
  },
  "track": "real_model"
}
```

## Configuration

```json
{
  "started_at_utc": "2026-10-14T02:59:18.783160+00:00",
  "app_revision": "53520f74461387e4c924e8b83295ba0a4bb70c90",
  "app_source_hashes": {
    "middleware\\demo_medical_workflow.py": "10cabb31d4ed224fe0b676b368fd49d709a26248642de72acae347a36854c3ed",
    "middleware\\demo_time.py": "f13c1df2c465ca661f779228b8469374a6d219aa9c5332c4fc0182d4946faeb6",
    "middleware\\demo_model.py": "6985b6c226324bb053d969cb7c6a9fb23b43a6f73e5c944e0dda35f7a6850443",
    "middleware\\interaction_delivery.py": "4482dc4c5837b8575b9e2ecf382093b667c82a182d6c6544babdc587ba56f21b",
    "middleware\\server.py": "b2ea74e1dea7e8cfeeaa314d0d707e12d74c5bdc355e3184b6542bd0e7127503",
    "middleware\\execution.py": "6164fe60d0c80076fc463b9610a66ad03c443ac10b27f603097796ff2d3fcf6f"
  },
  "harness_source_hashes": {
    "adapter.py": "8c06b73cfd4e44ca5e8c57bded39cd90b4edac085c9ba2aade2c4c3f41e23a77",
    "audit.py": "212c7082dc512f8b989e5d3d4427334ca2f7c6f78238f207716bc28a584e6706",
    "compare.py": "c4fae3c0361c2d9e3090b0928c8a7d20df27db86a36a641d6fe7f8a62b78004d",
    "harmonized_audit.py": "3d795e434f2b65eea706b3393cc8f33a96562557cdfbd59f5c8275dad62ffade",
    "observer_facts.py": "812e71a2b3d42837eb0c8f54ad37ff741769c668449306db960356cee6b8a29a",
    "runner.py": "df59f8986303aad15bd043b25d0bd0cc978e9ec1483fcac1e5daf19f1036f1b4",
    "scoring.py": "108c718e4ac52ce873aeab3c9a90e3a495cbb0e3abba5e72aa9f7ca2f3eaa0f5",
    "test_observer_facts.py": "962a83130ecdd37f3b1eeb53e4457d15a96a10e4f086aeca2838b840677ed006",
    "test_scoring.py": "b4c80f454264fa7c05fbbc4062cdbe75104cac03daa4dcfb0b61078e0110227a"
  },
  "dataset_hash": "3c7f2b7c62af0aec5abc688f9f0d7e6b646237c5893038082990a8131344b326",
  "clock": "2026-10-13T09:00:00+08:00",
  "timezone": "Asia/Macau",
  "model": "gpt-4.1-mini",
  "endpoint_type": "https://api.openai.com",
  "prompt_hash": "040557deb66614a15c6bbdb7b32e022d8e8e3aaa8b68ebde6dd5cb05262c7dc2",
  "temperature": 0,
  "max_decisions": 4,
  "runner_version": 1
}
```
