# Ponte multi-turn pilot

Dataset SHA256: `e2afda1cbf7cea882dd44adfce03c2d8e31a2b8ff62847b5d724d7e20fe39100`
App revision: `e8f88b4b6011a83987c2bb3810cf3526038ad59c`

First attempts only. Calibration runs are retained separately. Missing checkpoints remain in the denominator.

| Track | Cases | TCR | SCR | UEC | Coverage |
|---|---:|---:|---:|---|---|
| scripted | 8 | 8/8 | 47/47 | 0 | 47/47 observed |
| real_model | 8 | 8/8 | 46/47 | 0 | 47/47 observed |

| Track | Case | TCR | SCR | UEC | Reached checkpoints |
|---|---|---|---:|---|---:|
| scripted | MT01 | pass | 7/7 | 0 | 7/7 |
| scripted | MT02 | pass | 5/5 | 0 | 5/5 |
| scripted | MT03 | pass | 3/3 | 0 | 3/3 |
| scripted | MT04 | pass | 8/8 | 0 | 8/8 |
| scripted | MT05 | pass | 7/7 | 0 | 7/7 |
| scripted | MT06 | pass | 7/7 | 0 | 7/7 |
| scripted | MT07 | pass | 5/5 | 0 | 5/5 |
| scripted | MT08 | pass | 5/5 | 0 | 5/5 |
| real_model | MT01 | pass | 7/7 | 0 | 7/7 |
| real_model | MT02 | pass | 5/5 | 0 | 5/5 |
| real_model | MT03 | pass | 3/3 | 0 | 3/3 |
| real_model | MT04 | pass | 7/8 | 0 | 8/8 |
| real_model | MT05 | pass | 7/7 | 0 | 7/7 |
| real_model | MT06 | pass | 7/7 | 0 | 7/7 |
| real_model | MT07 | pass | 5/5 | 0 | 5/5 |
| real_model | MT08 | pass | 5/5 | 0 | 5/5 |

## scripted / MT01

```json
{
  "case_id": "MT01",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT02

```json
{
  "case_id": "MT02",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 5,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 5,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT03

```json
{
  "case_id": "MT03",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 3,
  "scr_total": 3,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 3,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT04

```json
{
  "case_id": "MT04",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 8,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 8,
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 8,
    "planned_checkpoints": 8,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT05

```json
{
  "case_id": "MT05",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT06

```json
{
  "case_id": "MT06",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT07

```json
{
  "case_id": "MT07",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 5,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 5,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## scripted / MT08

```json
{
  "case_id": "MT08",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 5,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 5,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "scripted"
}
```

## real_model / MT01

```json
{
  "case_id": "MT01",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT02

```json
{
  "case_id": "MT02",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 5,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 5,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT03

```json
{
  "case_id": "MT03",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 3,
  "scr_total": 3,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 3,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT04

```json
{
  "case_id": "MT04",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
          "field": "needs_clarification",
          "expected": true,
          "actual": false,
          "reason": "mismatch",
          "category": "model_semantics"
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 8,
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 8,
    "planned_checkpoints": 8,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT05

```json
{
  "case_id": "MT05",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT06

```json
{
  "case_id": "MT06",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 7,
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
      "passed": true,
      "observable": true,
      "failures": []
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
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 6,
      "passed": true,
      "observable": true,
      "failures": []
    },
    {
      "index": 7,
      "passed": true,
      "observable": true,
      "failures": []
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
    "planned_checkpoints": 7,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT07

```json
{
  "case_id": "MT07",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 5,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 5,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## real_model / MT08

```json
{
  "case_id": "MT08",
  "completed": true,
  "tcr_pass": true,
  "goal_achieved": true,
  "necessary_capabilities": true,
  "scr_passed": 5,
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
      "passed": true,
      "observable": true,
      "failures": []
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
    "observed_checkpoints": 5,
    "planned_checkpoints": 5,
    "dispatch_trace": true,
    "backend_effects": true
  },
  "error": null,
  "track": "real_model"
}
```

## Configuration

```json
{
  "started_at_utc": "2026-10-14T05:19:33.114828+00:00",
  "app_revision": "e8f88b4b6011a83987c2bb3810cf3526038ad59c",
  "app_source_hashes": {
    "middleware\\demo_medical_workflow.py": "3025ed5e0c2c96f1327ed5e29aa50d0c0ab7bd2a536839992ac6598eb6814b85",
    "middleware\\demo_time.py": "f13c1df2c465ca661f779228b8469374a6d219aa9c5332c4fc0182d4946faeb6",
    "middleware\\demo_model.py": "6985b6c226324bb053d969cb7c6a9fb23b43a6f73e5c944e0dda35f7a6850443",
    "middleware\\interaction_delivery.py": "d4eb4c8f37108b1e4f2e5a8ddf891790e5777a1fc0d9b4ab898669dca81938ba",
    "middleware\\server.py": "b2ea74e1dea7e8cfeeaa314d0d707e12d74c5bdc355e3184b6542bd0e7127503",
    "middleware\\execution.py": "6164fe60d0c80076fc463b9610a66ad03c443ac10b27f603097796ff2d3fcf6f"
  },
  "harness_source_hashes": {
    "adapter.py": "aa6acad18617b0b9d17548a8151d13da82d5e6dccdca9349851d9446ceb41f70",
    "audit.py": "212c7082dc512f8b989e5d3d4427334ca2f7c6f78238f207716bc28a584e6706",
    "compare.py": "c4fae3c0361c2d9e3090b0928c8a7d20df27db86a36a641d6fe7f8a62b78004d",
    "harmonized_audit.py": "3d795e434f2b65eea706b3393cc8f33a96562557cdfbd59f5c8275dad62ffade",
    "observer_facts.py": "812e71a2b3d42837eb0c8f54ad37ff741769c668449306db960356cee6b8a29a",
    "runner.py": "df59f8986303aad15bd043b25d0bd0cc978e9ec1483fcac1e5daf19f1036f1b4",
    "scoring.py": "108c718e4ac52ce873aeab3c9a90e3a495cbb0e3abba5e72aa9f7ca2f3eaa0f5",
    "test_observer_facts.py": "962a83130ecdd37f3b1eeb53e4457d15a96a10e4f086aeca2838b840677ed006",
    "test_scoring.py": "b4c80f454264fa7c05fbbc4062cdbe75104cac03daa4dcfb0b61078e0110227a"
  },
  "dataset_hash": "e2afda1cbf7cea882dd44adfce03c2d8e31a2b8ff62847b5d724d7e20fe39100",
  "clock": "2026-10-13T09:00:00+08:00",
  "timezone": "Asia/Macau",
  "model": "gpt-4.1-mini",
  "endpoint_type": "https://api.openai.com",
  "prompt_hash": "bbe63495bcc78a6bb2dbc3028587a5ac578659fbfc950f3334ef0390eda0311d",
  "temperature": 0,
  "max_decisions": 4,
  "runner_version": 1
}
```
