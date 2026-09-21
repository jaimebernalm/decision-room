# Repository workflow

Follow the numbered steps in [the implementation plan](<docs/product/Decision Room - Plan de implementacion.md>).

- When a plan step is complete, run the checks appropriate to that step, review
  the changes and create a local Git commit for that completed step. The user has
  requested this as the normal workflow; do not ask again each time.
- Keep commits focused and describe the final behavior and relevant validation.
  Do not mark incomplete steps as complete or manufacture commits representing
  historical states that were not actually saved.
- Report the commit hash and the checks performed when finishing the step.
- Push to GitHub only when the user explicitly requests it. A local commit and a
  remote push are separate actions.

This repository is intended to be public. Before committing, review staged files
for credentials, personal machine paths, private customer data and large generated
files. Maintain `.gitignore`: runtime state, downloaded datasets, private uploads,
environment files and credentials stay local. Keep source code, dependency locks,
documentation, dataset attribution and the small public reference fixtures in Git.
Never edit or discard the user's unrelated changes just to produce a clean commit.
