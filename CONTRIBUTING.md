# Contributing to Verifacts Backend

Welcome to the Verifacts engineering team! This guide will help you set up your development environment and understand our engineering standards.

## 🚀 Environment Setup

We use **Poetry** for dependency management to ensure deterministic builds across all micro-modules.

### 1. Installation

```bash
# Install Project Dependencies
poetry install
````

### 2\. Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

**Required Variables:**

  * `OPENAI_API_KEY`: For LLM extraction.
  * `FIRECRAWL_API_KEY`: For web scraping.
  * `GOOGLE_FACT_CHECK_KEY`: For verification.

### 3\. Running the Server

Start the hot-reloading development server:

```bash
poetry run uvicorn app.api.server:app --reload
```

-----

## 🌳 Git Workflow & Branching Strategy

We follow a strict branching model to keep our codebase stable. **Never push directly to `main`.**

### Branch Naming Convention

  * **Features:** `feat/short-description` (e.g., `feat/add-sentiment-node`)
  * **Bug Fixes:** `fix/short-description` (e.g., `fix/firecrawl-timeout`)
  * **Documentation:** `docs/short-description` (e.g., `docs/update-api-schema`)
  * **Chore/Refactor:** `chore/short-description` (e.g., `chore/bump-poetry-version`)

### The Workflow

1.  **Sync with Main:**
    ```bash
    git checkout main
    git pull origin main
    ```
2.  **Create Branch:**
    ```bash
    git checkout -b feat/my-new-feature
    ```
3.  **Code & Test:** Write your code and ensure `poetry run pytest` passes.
4.  **Push & PR:** Push your branch and open a Pull Request (PR) for review.

-----

## 📝 Commit Message Standards

We use **Conventional Commits** to automate our changelogs. Your commit message must look like this:

`<type>(<scope>): <short summary>`

### Types

  * `feat`: A new feature (e.g., adding a new LangGraph node).
  * `fix`: A bug fix.
  * `docs`: Documentation only changes.
  * `style`: Formatting, missing semi-colons, etc. (no code change).
  * `refactor`: A code change that neither fixes a bug nor adds a feature.
  * `perf`: A code change that improves performance.
  * `test`: Adding missing tests.
  * `chore`: Maintainance tasks (e.g., updating `.gitignore`).

### Examples

  * ✅ `feat(graph): add sentiment analysis node to workflow`
  * ✅ `fix(api): handle 404 error from Firecrawl`
  * ✅ `docs(readme): update setup instructions for Windows`
  * ❌ `Fixed the bug` (Too vague)
  * ❌ `Added new agent` (Missing scope)

-----

## 🛠️ How to Add a New Feature (The "Node" Workflow)

Adding intelligence to Veritas means adding a **Node** to the LangGraph. Follow this 4-step process:

### Step 1: Create the Logic (The Module)

Create a new file in `app/graph/nodes/`. It must accept `AgentState` and return a dictionary of updates.

  * *File:* `app/graph/nodes/sentiment.py`
  * *Function:* `async def sentiment_node(state: AgentState) -> Dict[str, Any]: ...`

### Step 2: Update the State

If your node produces new data (e.g., a "sentiment score"), define it in the shared state.

  * *File:* `app/graph/state.py`
  * *Action:* Add `sentiment_score: float` to the `AgentState` TypedDict.

### Step 3: Register in the Graph

Wire your new node into the orchestration flow.

  * *File:* `app/graph/workflow.py`
  * *Action:*
    1.  `workflow.add_node("sentiment", sentiment_node)`
    2.  Define when it runs (e.g., `workflow.add_edge("reader", "sentiment")`).

### Step 4: Expose via API (Optional)

If the frontend needs to see this data, update the response model.

  * *File:* `app/api/v1/models.py` (or `server.py`)
  * *Action:* Add the field to the Pydantic Response model.

-----

## 🧪 Testing Requirements

Before submitting a PR, ensure you have added tests for your new node.

```bash
# Run unit tests
poetry run pytest

# Run linting manually (Recommended)
poetry run ruff check .
```

## Pull Request Reviews
All PRs must be reviewed by at least one other team member. Look for:

  * Code quality and adherence to standards.
  * Proper testing coverage.
  * Clear and descriptive commit messages.


Thank you for contributing to Verifacts! Your efforts help us build a reliable and intelligent verification platform.