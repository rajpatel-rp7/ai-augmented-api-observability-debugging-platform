# Kubernetes manifests

Minimal demo deployment for the observability platform (local Kind/Minikube or a lab cluster).

These manifests are **not** production-hardened HA charts. Prefer managed Postgres, Elasticsearch, Redis, and Jaeger outside the cluster when possible.

## Build images

```bash
docker build -t observability-api:0.9.0 ./backend
docker build -t observability-frontend:0.9.0 \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  ./frontend
```

Load images into Kind if needed:

```bash
kind load docker-image observability-api:0.9.0
kind load docker-image observability-frontend:0.9.0
```

## Configure secrets

```bash
cp k8s/secret.example.yaml k8s/secret.yaml
# edit passwords / DATABASE_URL / OPENAI_API_KEY
```

Update `kustomization.yaml` to reference `secret.yaml` instead of `secret.example.yaml` before apply.

## Apply

```bash
kubectl apply -k k8s/
kubectl -n observability rollout status deploy/api
kubectl -n observability port-forward svc/api 8000:8000
kubectl -n observability port-forward svc/frontend 5173:80
```

## Notes

- API probes: liveness `/health`, readiness `/ready` (Postgres).
- Frontend image must be rebuilt when the public API URL changes (`VITE_API_BASE_URL`).
- Elasticsearch needs enough memory; adjust `ES_JAVA_OPTS` / limits on small nodes.
