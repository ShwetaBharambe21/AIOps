# SOP: Fixing ImagePullBackOff Errors

## Overview
This Standard Operating Procedure (SOP) details the steps required to diagnose and resolve `ImagePullBackOff` errors in a Kubernetes cluster. This error indicates that the Kubelet is repeatedly failing to pull the specified container image from the registry, preventing the associated Pod from starting. This SOP is critical for restoring service availability when deployments fail due to image access issues.

## Symptoms
*   **Pod Status:** Pods stuck in `ImagePullBackOff` or `ErrImagePull` status.
*   **Logs:** Pod logs showing repeated failure messages related to image pulling.
*   **Error Message:** The specific error message containing `ImagePullBackOff` or `ErrImagePull`.

## Detection
How to detect this issue:
*   **Automated alerts to configure:** Alerting on Pod status transitions to `ImagePullBackOff` or `ErrImagePull` for critical deployments.
*   **kubectl commands to check:**
    ```bash
    kubectl get pods -n <namespace> | grep ImagePullBackOff
    kubectl describe pod <pod-name> -n <namespace> | grep "Failed to pull image"
    ```
*   **Log patterns to look for:**
    *   `ErrImagePull: failed to pull and unpack image "<image-name>"`
    *   `dial tcp: lookup <registry-host> on <IP>:53: no such host` (Indicates DNS failure)

## Root Cause Analysis
`ImagePullBackOff` is a symptom, not the root cause. The root cause typically falls into one of three categories:

1.  **Incorrect Image Reference:** The image name, tag, or registry path is misspelled or does not exist (e.g., `nonexistent-registry.io/fake-app:v99.0`).
2.  **Network/DNS Failure:** The cluster nodes cannot resolve the registry host name (e.g., DNS failure for `nonexistent-registry.io`).
3.  **Authentication Failure:** The image exists, but the cluster lacks the necessary credentials (e.g., private registry requiring a secret).

## Prerequisites
*   **Access:** Read/Write access to the Kubernetes cluster (via `kubectl`).
*   **Tools:** `kubectl` configured for the target cluster.
*   **Information:** The correct, fully qualified image path (`registry.example.com/repo:tag`) and, if applicable, the required registry credentials (username/password or service account token).

## Step-by-Step Resolution

### Step 1: Triage
1.  **Identify the failing Pod:** Use `kubectl get pods -n <namespace>` to confirm the Pod is in `ImagePullBackOff`.
2.  **Gather Details:** Run `kubectl describe pod <pod-name> -n <namespace>`.
3.  **Analyze the Error:** Review the `Events` section of the `describe` output to pinpoint the exact failure message (e.g., DNS failure, manifest not found, unauthorized).

### Step 2: Identify Root Cause
Based on the error message, determine the failure type:

*   **Scenario A: DNS Failure (e.g., `no such host`):** The registry host name is unreachable or incorrectly configured in the cluster's DNS settings.
*   **Scenario B: Image Not Found/Typo:** The error indicates the image or tag does not exist (e.g., `manifest not found`).
*   **Scenario C: Authentication Failure:** The error indicates permission issues (e.g., `unauthorized`).

### Step 3: Apply Fix
Execute the fix based on the identified root cause:

**🛠️ Fix for Scenario B (Incorrect Image Reference/Typo):**
If the image name is incorrect, update the deployment manifest:
```bash
kubectl edit deployment <deployment-name> -n <namespace>
# Locate the container spec and update the image field:
# Example change: nonexistent-registry.io/fake-app:v99.0 -> correct-registry.io/app:v1.2.3
```

**🛠️ Fix for Scenario C (Authentication Failure):**
If the registry is correct but requires credentials, create or update the secret:
```bash
# Assuming Docker registry credentials:
kubectl create secret docker-registry my-registry-secret \
  --docker-server-address=<registry-host> \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email>
```
*Then, ensure the Pod/Deployment spec references this secret in `imagePullSecrets`.*

**🛠️ Fix for Scenario A (Network/DNS Failure):**
*   **Immediate Action:** Verify the registry host name is resolvable from a node within the cluster using `nslookup` or `dig`.
*   **Permanent Action:** Coordinate with the Platform/Network team to correct the DNS records or update the cluster's CoreDNS configuration.

### Step 4: Verify Resolution
1.  **Monitor Pod Status:** Wait for the Pod status to transition from `ImagePullBackOff` to `ContainerCreating`, and finally to `Running`.
    ```bash
    kubectl get pods -n <namespace> -w <pod-name>
    ```
2.  **Check Logs:** Verify that the application logs are streaming correctly, confirming the container started successfully.
    ```bash
    kubectl logs <pod-name> -n <namespace>
    ```

## Rollback Procedure
If the applied fix (e.g., changing the image tag or adding a secret) causes the Pod to fail or enter a new error state:

1.  **Revert Manifest:** Use `kubectl rollout undo deployment/<deployment-name> -n <namespace>` to revert the deployment to the last known good configuration.
2.  **Remove Secret (If applicable):** If the secret was added and caused issues, delete it:
    ```bash
    kubectl delete secret <secret-name> -n <namespace>
    ```

## Prevention
*   **Configuration best practices:** Always use fully qualified domain names (FQDNs) for image registries. Store registry credentials in dedicated Kubernetes Secrets and reference them via `imagePullSecrets`.
*   **Resource limits and requests guidance:** While not directly related to `ImagePullBackOff`, ensure that the nodes hosting the Pod have sufficient network bandwidth and DNS resolution capabilities to handle image pulls efficiently.
*   **Monitoring and alerting recommendations:** Implement alerts that trigger when the rate of `ImagePullBackOff` errors exceeds a defined threshold (e.g., 5 failures in 5 minutes) for critical services.

## Escalation
*   **Level 1 (SRE/DevOps):** Execute this SOP. If the issue is a simple typo or missing secret, resolution should occur here.
*   **Level 2 (Network/Platform Team):** Escalate if the root cause is determined to be a cluster-wide DNS failure, inability to reach the registry host, or core networking misconfiguration.
*   **Level 3 (Cloud Provider/Infrastructure):** Escalate if the issue is confirmed to be external (e.g., the registry itself is down or the VPC routing is broken).

## References
*   [Kubernetes Documentation: ImagePullBackOff](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
*   [Kubernetes Documentation: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
*   [Related SOP: Handling DNS Resolution Failures](link-to-internal-dns-sop)