# Jupyter Notebook Git Persistence

This chart can persist notebooks to your GitHub repository under `apps/notebook`.

## 1) Enable Git sync

Set in `jupyter/values.yaml`:

```yaml
gitSync:
  enabled: true
  repo: cukhoaimon/devoops-argocd
  branch: main
  notebooksPath: apps/notebook
  secretName: jupyter-git-token
  secretTokenKey: token
```

When enabled, the deployment does this:
- `initContainer` clones the repo into the notebook PVC at `/home/jovyan/work/repo`
- Jupyter root directory is set to `/home/jovyan/work/repo/apps/notebook`
- `git-autosync` sidecar commits and pushes notebook changes periodically
- commits are debounced: changes must remain unchanged for `gitSync.idleSeconds` before commit

## 2) Create GitHub token secret

Create a PAT with repo write access, then create the Kubernetes secret in `spark` namespace:

```bash
kubectl -n spark create secret generic jupyter-git-token \
  --from-literal=token='<YOUR_GITHUB_PAT>'
```

If secret already exists, update it:

```bash
kubectl -n spark delete secret jupyter-git-token
kubectl -n spark create secret generic jupyter-git-token \
  --from-literal=token='<YOUR_GITHUB_PAT>'
```

## 3) Push chart changes and let ArgoCD sync

```bash
git add jupyter
git commit -m "feat(jupyter): add optional git-backed notebook persistence"
git push origin main
```

ArgoCD will redeploy Jupyter in namespace `spark`.

## Notes

- This mechanism commits only changes under `apps/notebook`.
- Recommended: use a dedicated branch like `notebooks` for autosaves.
- The sidecar rebases before pushing, but real-time concurrent edits can still cause conflicts.
- Consider adding `apps/notebook/.gitignore` for `.ipynb_checkpoints/`.
