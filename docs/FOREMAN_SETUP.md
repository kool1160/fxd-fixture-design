# FXD Foreman Setup

## Repository settings

In GitHub repository settings, under Actions → General → Workflow permissions, enable:

- Read and write permissions
- Allow GitHub Actions to create and approve pull requests

The AI execution job remains read-only. A separate clean publishing job receives only the permissions needed to push a branch and open a pull request.

## OpenAI configuration

Create a dedicated OpenAI API project for FXD and add its key as the repository Actions secret:

```text
OPENAI_API_KEY
```

Do not commit an API key. Set a conservative project spending limit and alerts before running the Foreman.

## Running the Foreman

Open the Actions tab, choose **FXD Foreman**, and select **Run workflow**.

- Leave the milestone blank to run the first eligible milestone.
- Supply a milestone number to run a specific non-complete milestone.
- Keep generated pull requests as drafts until the workflow and validation are proven.

## Public-repository warning

The Foreman operates on a public repository. Do not place customer CAD, employer files, proprietary rule packs, private corrections, patent-sensitive descriptions, API keys, or vendor SDK binaries into its workspace or prompts.
