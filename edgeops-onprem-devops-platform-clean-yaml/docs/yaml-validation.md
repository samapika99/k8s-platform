# YAML and Helm validation

All Kubernetes manifests in `helm/edgeops/templates/` intentionally use expanded,
readable YAML. Avoid compact forms such as:

```yaml
ports: [{containerPort: 27017}]
```

Use:

```yaml
ports:
  - name: mongodb
    containerPort: 27017
    protocol: TCP
```

Validate before installation:

```bash
helm lint helm/edgeops
helm template edgeops helm/edgeops
```

If `kubeconform` is installed:

```bash
helm template edgeops helm/edgeops | kubeconform -strict
```

Then install:

```bash
microk8s helm3 upgrade --install edgeops ./helm/edgeops
```
