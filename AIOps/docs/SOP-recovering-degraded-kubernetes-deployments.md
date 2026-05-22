# SOP: Recovering Degraded Kubernetes Deployments

## Overview
This Standard Operating Procedure (SOP) details the steps required to diagnose and resolve `ImagePullBackOff` or `ImagePullError` states in Kubernetes deployments. This SOP applies when a Pod fails to start because the cluster cannot successfully pull the required container image from the specified registry.

## Symptoms
*   **Pod Status:** Pod remains in `ImagePullBackOff` or `ErrImagePull` state.
*   **kubectl describe output:** The `Events` section of the Pod description shows errors related to image pulling, specifically mentioning `failed to resolve reference` or `failed to do request`.
*   **Logs:** Container logs are unavailable or show repeated pull failure messages.

## Detection
How to detect this issue:
*   **Automated alerts to configure:** Alerting should trigger on a sustained increase in Pods reporting `ImagePullBackOff` or `ErrImagePull` status within a namespace.
*   **kubectl commands to check:**
    ```bash
    kubectl get pods -n <namespace> | grep -E "ImagePullBackOff|ErrImagePull"
    kubectl describe pod <pod-name> -n <namespace>
    ```
*   **Log patterns to look for:**
    *   `failed to pull and unpack image`
    *   `failed to resolve reference`
    *   `dial tcp: lookup <registry-host> on ...: no such host`

## Root Cause Analysis
The primary root cause for `ImagePullBackOff` is typically one of the following:

1.  **Incorrect Image Reference (Typo):** The image name, tag, or registry path specified in the Deployment YAML is incorrect.
2.  **Network/DNS Failure:** The Kubernetes worker nodes cannot resolve the hostname of the container registry (e.g., DNS failure, firewall blockage).
3.  **Authentication Failure:** The registry requires credentials (username/password, token) that are not provided or are expired.
4.  **Registry Downtime:** The external container registry itself is unavailable.

## Prerequisites
*   **Access:** Read/Write access to the Kubernetes cluster (via `kubectl`).
*   **Tools:** `kubectl` CLI installed and configured for the target cluster.
*   **Information:** The correct, fully qualified domain name (FQDN) of the container registry and the exact image tag.

## Step-by-Step Resolution

### Step 1: Triage
1.  **Check Pod Status:** Use `kubectl get pods -n <namespace>` to confirm the affected Pods are in `ImagePullBackOff`.
2.  **Gather Details:** Run `kubectl describe pod <pod-name> -n <namespace>` and examine the `Events` section.
3.  **Identify Error:** Determine the specific error message (e.g., `failed to resolve reference`, `unauthorized`, etc.).

### Step 2: Identify Root Cause
Based on the error message:

*   **If the error is `no such host` or DNS related:** The registry hostname is unreachable or misspelled. Proceed to Step 2A.
*   **If the error is `unauthorized` or `forbidden`:** Authentication is missing or invalid. Proceed to Step 2B.
*   **If the error is vague or points to a non-existent resource:** The image path or tag is likely incorrect. Proceed to Step 2C.

**Step 2A: DNS/Network Failure (Example: `no such host`)**
*   Verify the registry hostname is correct.
*   Check cluster network policies and DNS resolution settings on the worker nodes.

**Step 2B: Authentication Failure**
*   Confirm the registry requires credentials.
*   Create or update the Kubernetes Secret containing the registry credentials:
    ```bash
    kubectl create secret docker-registry <secret-name> \
      --docker-server=<registry-host> \
      --docker-username=<username> \
      --docker-password=<password> \
      --namespace=<namespace>
    ```
*   Ensure the Deployment YAML references this secret in the `imagePullSecrets` field.

**Step 2C: Incorrect Image Reference (Example: `nonexistent-registry.io`)**
*   Consult the source of truth (e.g., CI/CD pipeline, Git repository) to obtain the correct image path and tag.
*   The registry host (`nonexistent-registry.io`) is incorrect or unreachable.

### Step 3: Apply Fix
**Action:** Edit the Deployment manifest to correct the image reference.

1.  **Edit Deployment:**
    ```bash
    kubectl edit deployment <deployment-name> -n <namespace>
    ```
2.  **Update Image:** Locate the `spec.template.spec.containers` section and change the `image:` field from the incorrect value to the correct, fully qualified image path:
    *   **Before (Incorrect):** `image: nonexistent-registry.io/fake-app:v99.0`
    *   **After (Correct):** `image: correct-registry.io/fake-app:v1.2.3`

*(If authentication was the root cause, ensure the `imagePullSecrets` block is added/updated in the Deployment spec.)*

### Step 4: Verify Resolution
1.  **Monitor Pods:** Wait for the Deployment to roll out the new image.
    ```bash
    kubectl rollout status deployment/<deployment-name> -n <namespace>
    ```
2.  **Check Status:** Verify that the Pods transition successfully to `Running` and `Ready`.
    ```bash
    kubectl get pods -n <namespace>
    ```
3.  **Validate Logs:** Check the application logs to ensure the application started successfully and is processing requests.
    ```bash
    kubectl logs <pod-name> -n <namespace>
    ```

## Rollback Procedure
If the fix (new image/deployment) causes unexpected application failures or instability:

1.  **Immediate Rollback:** Trigger a rollback to the last known good revision.
    ```bash
    kubectl rollout undo deployment/<deployment-name> -n <namespace>
    ```
2.  **Verification:** Monitor the Pod status and application logs to confirm the service has returned to its stable state.

## Prevention
*   **Configuration best practices:**
    *   Always use fully qualified domain names (FQDNs) for image registries.
    *   Store all registry credentials in dedicated Kubernetes Secrets and reference them via `imagePullSecrets`.
    *   Implement mandatory linting/validation checks in CI/CD pipelines to validate image paths before deployment.
*   **Resource limits and requests guidance:** While not directly related to image pulling, ensure that the Service Account used by the Pod has necessary network permissions (DNS resolution, egress) to reach external registries.
*   **Monitoring and alerting recommendations:**
    *   Set up alerts for `ImagePullBackOff` status changes.
    *   Implement synthetic transaction monitoring that validates the availability of the service endpoint.

## Escalation
*   **Level 1 (SRE/DevOps):** Attempting Steps 1-4 of this SOP.
*   **Level 2 (Platform Engineering):** If the root cause is determined to be a cluster-wide DNS failure or network policy issue that cannot be resolved by the application team.
*   **Level 3 (Cloud/Network Team):** If the issue is confirmed to be external (e.g., the entire external registry is down, or the cluster's underlying network infrastructure is compromised).

## References
*   [Kubernetes Documentation: ImagePullBackOff](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
*   [Kubernetes Documentation: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
*   [Related SOP: Network Troubleshooting in Kubernetes](link-to-internal-network-sop)