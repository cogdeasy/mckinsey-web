# Kubernetes manifests

A Kustomize base with one overlay per environment. Render an overlay before applying it:

```bash
kubectl kustomize overlays/dev
```

The base is deliberately environment agnostic: replica counts, hostnames, image tags, the issuer
and the log level all come from the overlay. Runtime secrets are never rendered from this
repository. Each overlay declares an `ExternalSecret` that projects the Secrets Manager entries
created by Terraform into a `claims-intake-runtime` secret, which the workloads consume with
`envFrom`.

Database migrations run as an init container on the API deployment, so a rollout cannot serve
traffic against an unmigrated schema.
