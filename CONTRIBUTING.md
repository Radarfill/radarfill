# Contributing to RadarFill

## Workflow
1. **Open or pick an issue** before starting work. Use the templates.
2. **Branch from `main`** with a name like `<type>/<short-name>`, for example `feat/cloud-masks`, `fix/s1-nodata` or `docs/data-card`.
3. **Commit small and often**, using [Conventional Commits](https://www.conventionalcommits.org/):
   `feat(data_kit): add field curve extraction`, `fix(track-a): ...`, `docs: ...`.
4. **Open a pull request** into `main`, fill in the template, and get **one review** from a teammate.
5. **Squash-merge** once checks pass. Nobody pushes directly to `main`.

## Where code goes
| Folder | Owner |
|---|---|
| `code/data_kit/` | everyone. Changes need a review from **both** other members, because all tracks depend on it |
| `code/member_a/`, `member_b/`, `member_c/` | the track owner |
| `code/app/` | everyone, one module each |

## Research rules (a PR must not break these)
- **Never commit data.** No `dataset/`, `.npy`, `.parquet` or large outputs. Put results in `outputs/`, which is git-ignored.
- **Past only.** At cut-off *t*, use only data dated ≤ *t*. That applies to filling, scaling and features.
- **Folds.** Train 1–3, validate 4, test 5. Scaling statistics come from the training folds only. Touch the test fold once.
- **Leak test.** Any change to the Data Kit or to model inputs must keep the leak test passing.
- **Data decisions.** Any new threshold, filter or mapping goes into `docs/data_decisions.md` in the same PR.

## Code style
- Python 3.12. Follow the style of the surrounding code.
- Scripts take command-line arguments, write only to `outputs/`, and never write inside `dataset/`.
- Fix random seeds, and put the commands that reproduce a result in the PR description.

## Environment
If you add a package, update `requirements.txt` with
`uv pip freeze --python .venv/bin/python > requirements.txt` and mention it in the PR.
