# Xolaris Security Tool Adapter Framework

## Architecture Explanation

The adapter framework is the **hexagonal port** between external security
scanners and the Xolaris platform core.

Adapters are responsible for:

1. Authentication
2. Scope validation
3. **Mandatory PolicyEngine evaluation** (never execute without ALLOW)
4. Tool execution (subprocess)
5. Metadata / metrics collection
6. Parsing vendor stdout into structured JSON
7. Returning a **`RawResult` only**

Adapters **must never** create `SecurityFindingObject`. That conversion is
owned exclusively by the Normalization Service:

```
Security Tool
    ↓
Tool Adapter  ──► RawResult
    ↓
Normalization Service
    ↓
SecurityFindingObject
```

Existing modules (Decision Engine, Context Manager, Prompt Builder, Provider
Factory, Canonical Models, Normalization Service, Policy Engine) are **not
modified**. The adapter layer **calls** PolicyEngine via dependency injection.

---

## Sequence Diagram

```mermaid
sequenceDiagram
    participant Caller
    participant Factory as AdapterFactory
    participant Adapter as BaseToolAdapter
    participant Scope as ScopeValidator
    participant Policy as PolicyEngine
    participant Tool as Scanner Binary
    participant Norm as NormalizationService

    Caller->>Factory: create(tool, config)
    Factory->>Adapter: construct(+ DI)
    Caller->>Adapter: run(context)
    Adapter->>Adapter: initialize()/authenticate()
    Adapter->>Scope: validate(context)
    Adapter->>Policy: evaluate(PolicyInput)
    alt verdict != ALLOW
        Adapter-->>Caller: RawResult(POLICY_DENIED)
    else ALLOW
        Adapter->>Tool: execute(command)
        Tool-->>Adapter: stdout/stderr/exit
        Adapter->>Adapter: parse() + collect_metadata()
        Adapter->>Adapter: build_raw_result()
        Adapter-->>Caller: RawResult
        Caller->>Norm: normalize(tool, raw_output, ctx)
        Norm-->>Caller: SecurityFindingObject[]
    end
```

---

## Class Diagram

```mermaid
classDiagram
    class BaseToolAdapter {
        <<abstract>>
        +run(context) RawResult
        +initialize()
        +authenticate()
        +validate_scope()
        +validate_policy()
        +prepare()
        +execute() CommandResult
        +collect_metadata()
        +parse()*
        +build_raw_result() RawResult
        +cleanup()
        +health() bool
        +version() str
        +build_command()* List~str~
    }

    class AdapterRegistry {
        +register(name)$
        +unregister(name)$
        +get(name)$ Type
        +list()$
    }

    class AdapterFactory {
        +create(tool, config) BaseToolAdapter
        +available_tools()
    }

    class RawResult {
        +execution_id
        +tenant_id
        +tool_name
        +raw_output
        +status
        +metadata
    }

    class NucleiAdapter
    class ProwlerAdapter
    class TrivyAdapter
    class CheckovAdapter
    class PolicyEngine

    BaseToolAdapter <|-- NucleiAdapter
    BaseToolAdapter <|-- ProwlerAdapter
    BaseToolAdapter <|-- TrivyAdapter
    BaseToolAdapter <|-- CheckovAdapter
    AdapterFactory --> AdapterRegistry
    AdapterFactory --> BaseToolAdapter
    BaseToolAdapter --> PolicyEngine
    BaseToolAdapter --> RawResult
```

---

## Folder Structure

```
src/adapters/
├── base/
│   ├── base_adapter.py
│   ├── raw_result.py
│   ├── adapter_config.py
│   ├── adapter_exception.py
│   ├── registry.py
│   └── factory.py
├── common/
│   ├── authentication.py
│   ├── scope_validator.py
│   ├── metadata_collector.py
│   ├── execution_context.py
│   └── retry.py
├── nuclei|prowler|trivy|checkov/
│   ├── adapter.py
│   ├── parser.py
│   └── config.py
├── bootstrap.py
└── ARCHITECTURE.md
```

---

## Adding a Future Adapter

**Full team guide (checklist, MCP/agents, examples):** [docs/adapters/README.md](../../../docs/adapters/README.md)

Quick steps:

1. Create `src/adapters/<tool>/{config,parser,adapter}.py`
2. Subclass `BaseToolAdapter`
3. Decorate with `@AdapterRegistry.register("<tool>")`
4. Implement `build_command` + `parse`
5. Add matching **normalizer** in `normalization/adapters/`
6. Import the module from `bootstrap.py`
7. Optional: wire `scan_ingest` `_CONFIGS` + simulate sample payload

No business-logic changes required in Policy Engine core or downstream engines.

---

## Usage

```python
from src.adapters import AdapterFactory, AdapterRegistry
from src.adapters.nuclei import NucleiAdapterConfig
from src.adapters.common import AdapterExecutionContext

adapter = AdapterFactory().create("nuclei", NucleiAdapterConfig())
raw = adapter.run(context)          # RawResult
# later: NormalizationService().normalize("nuclei", raw.raw_output, norm_ctx)
```
