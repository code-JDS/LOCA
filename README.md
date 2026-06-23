# LOCA: Logical Chain Augmentation for Olympiad-Level Physics Reasoning

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

**LOCA (Logical Chain Augmentation)** is a novel multi-agent framework for complex physics reasoning, capable of solving Olympiad-level physics problems (IPhO/CPhO). LOCA leverages iterative review and augmentation to enhance LLM reasoning quality on challenging scientific problems.

## Installation

### Prerequisites
- Python 3.12+
- LLM API key
- [uv](https://docs.astral.sh/uv/) (recommended)

### Setup

1. **Clone the repository**
```bash
git clone xxx
cd LOCA
```

2. **Install dependencies**

Using uv (recommended):
```bash
uv sync
```

## Project Structure

```
LOCA/
├── src/                         # Source code
│   ├── loca/                    # LOCA implementation (Solver, Reviewers, Augmentation)
│   ├── vanilla_review/          # Vanilla review implementation (Baseline)
│   ├── single_llm.py            # Single LLM solver (Baseline)
│   ├── api/                     # LLM API interfaces (OpenAI, Anthropic, LiteLLM)
│   ├── utils.py                 # Common utilities
│   └── ...
├── configs/                     # Configuration files
├── problem_set/                 # Test datasets
├── test_results/                # Evaluation results
└── scripts/                     # Analysis scripts
```

## Usage
### Running LOCA
```bash
uv run main.py --config PATH_TO_YAML --config-name CONFIG_NAME_IN_YAML
```
