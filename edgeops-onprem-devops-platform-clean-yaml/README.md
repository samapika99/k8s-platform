# EdgeOps — On-Prem Kubernetes Operations & Deployment Platform

A realistic DevOps/platform engineering lab designed for a single-node MicroK8s/Kubernetes environment.

## Business scenario

An enterprise operates customer/branch sites with on-prem Kubernetes clusters. A central operations platform provides:

- Cluster/node/pod/PVC health
- Application inventory
- Telemetry collection
- Incident detection
- Incident acknowledgement/resolution
- Deployment history
- Audit events
- Real-time dashboard
- GitOps deployment through Argo CD
- CI/CD through GitHub Actions
- Prometheus/Grafana observability
- Loki/Promtail logging
- Trivy security scanning

The single-node version runs everything on one MicroK8s node. The architecture is intentionally extensible to multiple sites later.

## Architecture

```text
                        React Dashboard
                              |
                           Ingress
                              |
                           FastAPI
                 +------------+-------------+
                 |            |             |
              MongoDB       Redis        Kafka
                                            |
                                      +-----+------+
                                      |            |
                                  Telemetry      Incident
                                    Worker        Engine
                                      |
                              EdgeOps Kubernetes Agent
                                      |
                                  MicroK8s API
                                      |
                    +-----------------+----------------+
                    |                 |                |
                  Pods              Nodes             PVCs

Prometheus --> Grafana
Kubernetes stdout --> Promtail --> Loki --> Grafana

GitHub --> GitHub Actions --> GHCR --> GitOps repo --> Argo CD --> MicroK8s
```

## Repository

```text
edgeops-onprem-devops-platform/
├── services/
│   ├── api/
│   ├── worker/
│   ├── agent/
│   └── web/
├── helm/edgeops/
├── argocd/
├── monitoring/
├── docker-compose.yml
├── scripts/
├── .github/workflows/
├── Makefile
└── docs/
```

## Phase 1: Docker Compose

Use this to understand the application before Kubernetes.

```bash
docker compose up --build -d
docker compose ps

curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Open:

- http://localhost:5173
- http://localhost:8000/docs
- http://localhost:9090
- http://localhost:3000

Grafana:

```text
admin / admin
```

Run the business demo:

```bash
./scripts/demo.sh
```

## Phase 2: Single-node MicroK8s

Recommended for this project.

```bash
microk8s status --wait-ready
microk8s enable dns
microk8s enable ingress
microk8s enable helm3
microk8s enable hostpath-storage
```

If you want a local registry:

```bash
microk8s enable registry
```

Build and push:

```bash
docker build -t localhost:32000/edgeops-api:dev services/api
docker build -t localhost:32000/edgeops-worker:dev services/worker
docker build -t localhost:32000/edgeops-agent:dev services/agent
docker build -t localhost:32000/edgeops-web:dev services/web

docker push localhost:32000/edgeops-api:dev
docker push localhost:32000/edgeops-worker:dev
docker push localhost:32000/edgeops-agent:dev
docker push localhost:32000/edgeops-web:dev
```

Install:

```bash
microk8s helm3 upgrade --install edgeops ./helm/edgeops \
  --set api.image.repository=localhost:32000/edgeops-api \
  --set api.image.tag=dev \
  --set worker.image.repository=localhost:32000/edgeops-worker \
  --set worker.image.tag=dev \
  --set agent.image.repository=localhost:32000/edgeops-agent \
  --set agent.image.tag=dev \
  --set web.image.repository=localhost:32000/edgeops-web \
  --set web.image.tag=dev
```

Check:

```bash
microk8s kubectl get pods -n edgeops -o wide
microk8s kubectl get svc -n edgeops
microk8s kubectl get ingress -n edgeops
microk8s kubectl get pvc -n edgeops
```

## Phase 3: GitHub Actions

Workflow:

```text
.github/workflows/ci-cd.yml
```

It performs:

1. Python tests
2. Frontend tests/build
3. Helm lint
4. Trivy filesystem scan
5. Docker build
6. Trivy image scan
7. GHCR push
8. GitOps Helm tag update

Change these placeholders:

```text
YOUR_GITHUB_USER
```

in:

```text
helm/edgeops/values.yaml
argocd/application.yaml
```

## Phase 4: Argo CD

```bash
microk8s kubectl create namespace argocd

microk8s kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Then update `argocd/application.yaml` with your GitHub repository.

```bash
microk8s kubectl apply -f argocd/application.yaml
```

Port-forward:

```bash
microk8s kubectl -n argocd port-forward svc/argocd-server 8081:443
```

## Phase 5: Observability

Prometheus/Grafana:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring \
  prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```

Loki:

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm upgrade --install loki grafana/loki \
  -n monitoring --create-namespace \
  --set loki.auth_enabled=false

helm upgrade --install promtail grafana/promtail \
  -n monitoring \
  --set config.clients[0].url=http://loki-gateway.monitoring.svc.cluster.local/loki/api/v1/push
```

## Real incident exercises

### 1. Elasticsearch-style storage incident

Fill a PVC or temporarily reduce available storage. Observe:

```bash
kubectl get pvc -n edgeops
kubectl describe pvc -n edgeops
kubectl get events -n edgeops --sort-by=.lastTimestamp
```

Then inspect the incident dashboard.

### 2. ImagePullBackOff

```bash
kubectl -n edgeops set image deployment/edgeops-api \
  api=localhost:32000/edgeops-api:does-not-exist
```

Debug:

```bash
kubectl get pods -n edgeops
kubectl describe pod -n edgeops <pod>
```

Restore the image.

### 3. CrashLoopBackOff

Change the MongoDB URI:

```bash
kubectl -n edgeops set env deployment/edgeops-api \
  MONGO_URI=mongodb://wrong-host:27017
```

Debug:

```bash
kubectl logs -n edgeops deployment/edgeops-api
kubectl describe pod -n edgeops <pod>
```

### 4. Kafka consumer outage

```bash
kubectl -n edgeops scale deployment edgeops-worker --replicas=0
```

Send telemetry and observe event backlog behavior.

Restore:

```bash
kubectl -n edgeops scale deployment edgeops-worker --replicas=1
```

### 5. GitOps drift

```bash
kubectl -n edgeops scale deployment edgeops-api --replicas=5
```

Argo CD should reconcile the desired Git state.

### 6. Readiness failure

Change the readiness endpoint and observe:

```bash
kubectl get pods -n edgeops
kubectl describe pod -n edgeops <pod>
```

## Senior DevOps extensions

After the base project works, add:

- MongoDB replica set
- Kafka partitions/consumer autoscaling
- Redis HA
- OpenTelemetry + Tempo
- Argo Rollouts canary deployment
- Kyverno admission policies
- Cosign image signing
- Syft SBOM
- cert-manager TLS
- External Secrets/Vault
- MinIO backup target
- Velero
- NetworkPolicies
- PodDisruptionBudgets
- topology spread constraints
- multi-environment GitOps
- multi-cluster agent registration

## Useful interview statement

"I built an on-prem Kubernetes operations platform for monitoring cluster resources and applications, collecting telemetry through an agent and Kafka, storing operational state in MongoDB, exposing metrics through Prometheus, visualizing through Grafana, and deploying applications through GitHub Actions and Argo CD GitOps. I also implemented failure scenarios around storage, Kafka, image pulls, readiness and deployment drift."

## Important single-node limitation

This lab is intentionally single-node. Do not claim Kubernetes HA or node-level fault tolerance. The architecture is designed so that additional MicroK8s nodes/clusters can be introduced later.
