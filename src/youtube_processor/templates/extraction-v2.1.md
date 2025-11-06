# Video Extraction Template v2.1 - Knowledge Synthesis Focus

**Purpose**: Extract reusable knowledge units for LLM-consumable knowledge base

**Output**: Raw knowledge units that will be synthesized into topic documents

---

## Video Metadata (For Tracking Only)

**Video ID**: [ID]  
**Title**: [Title]  
**URL**: [YouTube URL]
**Channel**: [Channel Name]
**Date Published**: [YYYY-MM-DD]
**Extraction Date**: [YYYY-MM-DD]  
**Extractor**: [Tool/Person]

**Key Timestamps** (optional):
- [Topic]: [MM:SS-MM:SS]
- [Topic]: [MM:SS-MM:SS]

**Note**: Video metadata is for tracking only. Final knowledge documents will NOT reference videos.

---

## KNOWLEDGE UNITS EXTRACTION

The sections below extract reusable knowledge that will be synthesized across videos.

---

## 1. Techniques Extracted

### Technique: [Unique Name]

**ID**: `technique-[short-slug]` (e.g., `technique-memory-per-user`)

**What It Does**: [Clear 1-sentence description]

**Problem It Solves**: [What pain point this addresses]

**When to Use**:
- [Scenario 1]
- [Scenario 2]

**When NOT to Use**:
- [Anti-pattern scenario 1]
- [Anti-pattern scenario 2]

**Step-by-Step Implementation**:
```
1. [Step with technical details]
2. [Step with technical details]
3. [Step with technical details]
```

**Code Example**:
```python
# Complete working example
[code here]
```

**Prerequisites**:
- [Technical prerequisite 1]
- [Technical prerequisite 2]

**Common Pitfalls**:
- [Pitfall 1]: [How to avoid]
- [Pitfall 2]: [How to avoid]

**Variations**:
- [Variation 1]: [When to use]
- [Variation 2]: [When to use]

**Related Techniques**: [technique-id-1, technique-id-2]

---

## 2. Patterns Extracted

### Pattern: [Unique Name]

**ID**: `pattern-[short-slug]` (e.g., `pattern-self-modifying-agent`)

**Intent**: [What problem does this pattern solve?]

**Context**: [When is this pattern applicable?]

**Solution Structure**:
```
Component A → Component B → Component C
[Diagram or description]
```

**Implementation**:
```python
# Code showing the pattern
[code here]
```

**Consequences**:
- **Benefits**: [What you gain]
- **Tradeoffs**: [What you sacrifice]

**Example Use Cases**: [use-case-id-1, use-case-id-2]

**Related Patterns**: [pattern-id-1, pattern-id-2]

---

## 3. Use Cases Extracted

### Use Case: [Unique Name]

**ID**: `use-case-[short-slug]` (e.g., `use-case-multi-tenant-agents`)

**Problem Statement**: [Clear problem description]

**Solution Overview**: [How this use case solves it]

**Target Users**: [Who this is for]

**Technical Approach**:
- Architecture: [High-level approach]
- Key Components: [What you need]
- Implementation: [How to build]

**Success Criteria**: [How to know it's working]

**Techniques Used**: [technique-id-1, technique-id-2]

**Patterns Used**: [pattern-id-1, pattern-id-2]

**Example Implementation**:
```python
# Complete example
[code here]
```

**Challenges & Solutions**:
- [Challenge 1]: [How solved]
- [Challenge 2]: [How solved]

---

## 4. Capabilities Catalog

### Capability: [Feature Name]

**ID**: `capability-[short-slug]` (e.g., `capability-memory-blocks`)

**What It Does**: [Clear description]

**How It Works**: [Technical mechanism]

**Configuration**:
```yaml
# Example configuration
setting: value
```

**API Signature**:
```python
function_name(param: Type) -> ReturnType
```

**Limitations**:
- [Limitation 1]
- [Limitation 2]

**Workarounds**: [If available]

**Used In Techniques**: [technique-id-1, technique-id-2]

---

## 5. Integration Methods

### Integration: [System/Tool Name]

**ID**: `integration-[short-slug]` (e.g., `integration-postgres-vector`)

**Purpose**: [What this integration enables]

**Connection Method**: [Protocol, API, etc.]

**Setup Steps**:
```bash
# Installation/configuration
command1
command2
```

**Code Example**:
```python
# How to connect and use
[code here]
```

**Configuration Options**:
```yaml
option1: value1  # Purpose
option2: value2  # Purpose
```

**Common Issues**:
- [Issue 1]: [Solution]
- [Issue 2]: [Solution]

**Alternative Approaches**: [Other ways to integrate]

---

## 6. Anti-Patterns Catalog

### Anti-Pattern: [What NOT to Do]

**ID**: `antipattern-[short-slug]`

**Bad Approach**: [Description]

**Why It Fails**: [Technical reasons]

**Example of Bad Code**:
```python
# Don't do this
[bad code]
```

**Correct Approach**: [What to do instead]

**Example of Good Code**:
```python
# Do this instead
[good code]
```

**How to Recognize**: [Warning signs]

---

## 7. Architecture Components

### Component: [Component Name]

**ID**: `component-[short-slug]`

**Purpose**: [What this component does]

**Type**: [Service | Library | Tool | Infrastructure]

**Interfaces**:
- Input: [What it receives]
- Output: [What it produces]

**Dependencies**: [What it needs]

**Configuration**:
```yaml
# Example config
setting: value
```

**Integration Points**: [How it connects to other components]

---

## 8. Troubleshooting Knowledge

### Issue: [Problem Description]

**ID**: `issue-[short-slug]`

**Symptoms**: [What user sees]

**Root Cause**: [Technical explanation]

**Diagnostic Steps**:
```bash
# How to diagnose
command1
command2
```

**Solution**:
```bash
# How to fix
fix1
fix2
```

**Prevention**: [How to avoid]

**Related Issues**: [issue-id-1, issue-id-2]

---

## 9. Configuration Recipes

### Configuration: [Purpose/Scenario]

**ID**: `config-[short-slug]`

**When to Use**: [Scenario]

**Full Configuration**:
```yaml
# Complete configuration with explanations
setting1: value1  # Why this value
setting2: value2  # Purpose
```

**Minimal Configuration**:
```yaml
# Minimum required
setting1: value1
```

**Production Configuration**:
```yaml
# Production-ready settings
setting1: prod_value1
setting2: prod_value2
```

---

## 10. Code Snippets Library

### Snippet: [What It Does]

**ID**: `snippet-[short-slug]`

**Purpose**: [Use case]

**Code**:
```python
# Complete, working, copy-paste ready
[code here]
```

**Input Example**:
```
[input]
```

**Output Example**:
```
[output]
```

**Used In**: [technique-id or pattern-id where this appears]

---

## METADATA FOR SYNTHESIS

**Knowledge Units Extracted**:
- Techniques: [count]
- Patterns: [count]
- Use Cases: [count]
- Capabilities: [count]
- Integrations: [count]
- Anti-Patterns: [count]
- Components: [count]
- Issues: [count]
- Configs: [count]
- Snippets: [count]

**Topics Covered**: [tag1, tag2, tag3]

**Technologies Referenced**: [tech1, tech2, tech3]

**Synthesis Notes**: [Any notes about how to group/synthesize this knowledge]

---

## EXTRACTION CHECKLIST

- [ ] All techniques identified with unique IDs
- [ ] All patterns identified with unique IDs
- [ ] All use cases identified with unique IDs
- [ ] Code examples are complete and runnable
- [ ] Cross-references use consistent IDs
- [ ] Anti-patterns documented with corrections
- [ ] Technical details sufficient for implementation
- [ ] No video-specific references in knowledge units

---

**End of Extraction**