# Operations Runbook

## API is down

```bash
kubectl get pods -n edgeops
kubectl describe pod -n edgeops <pod>
kubectl logs -n edgeops deployment/edgeops-api
kubectl get events -n edgeops --sort-by=.lastTimestamp
```

Check:

- readiness
- MongoDB
- Redis
- Kafka
- resource limits

## MongoDB unavailable

```bash
kubectl get pod -n edgeops -l app=edgeops-mongodb
kubectl logs -n edgeops statefulset/edgeops-mongodb
kubectl get pvc -n edgeops
```

## Kafka unavailable

```bash
kubectl get pod -n edgeops -l app=edgeops-kafka
kubectl logs -n edgeops deployment/edgeops-kafka
```

## Worker not processing telemetry

```bash
kubectl logs -n edgeops deployment/edgeops-worker
kubectl get pods -n edgeops
```

Check Kafka and MongoDB connectivity.

## GitOps drift

```bash
argocd app get edgeops
argocd app diff edgeops
argocd app sync edgeops
```

## High storage

```bash
kubectl get pvc -n edgeops
kubectl describe pvc -n edgeops <pvc>
df -h
```

Then inspect Elasticsearch/Loki/other application data if installed.
