# SOP: Resolving ImagePullBackOff/CrashLoopBackOff in Kubernetes Pods

## Overview
This Standard Operating Procedure (SOP) details the steps required to diagnose and resolve pod failures characterized by `ImagePullBackOff` or subsequent `CrashLoopBackOff` states. This SOP applies when a pod fails to start because it cannot successfully pull the required container image from the specified registry.

## Symptoms
*   **Pod Status:** Pod remains in `ImagePullBackOff` or `Pending` state.
*   **Pod Status:** Pod repeatedly transitions through `CrashLoopBackOff` (if the image was pulled but failed immediately).
*   **kubectl describe output:** The `Events` section shows messages like `Failed to pull image`, `ErrImagePull`, or `Failed to resolve reference`.
*   **Specific Error:** The error message includes `dial tcp: lookup [registry.host] on [IP]:53: no such host`.

## Detection
**Automated alerts to configure:**
*   Alerting on Pod status remaining in `ImagePullBackOff` or `Pending` for more than 5 minutes.
*   Alerting on high rates of `ImagePullBackOff` events across namespaces.

**kubectl commands to check:**
1.  `kubectl get pods -n <namespace>` (Check for `ImagePullBackOff` status).
2.  `kubectl describe pod <pod-name> -n <namespace>` (Review the `Events` section for detailed pull failure reasons).
3.  `kubectl get events -n <namespace>` (Check cluster-wide events related to the pod).

**Log patterns to look for:**
*   `Failed to pull and unpack image`
*   `ErrImagePull`
*   `failed to resolve reference`
*   `no such host`

## Root Cause Analysis
The failure to pull an image is typically caused by one of the following issues:

1.  **Incorrect Image Reference (Most Common):** The image name, tag, or registry host specified in the Deployment/Pod YAML is misspelled or does not exist.
2.  **Network/DNS Failure:** The Kubernetes worker node cannot resolve the registry host's DNS name (e.g., `nonexistent-registry.io`). This indicates a cluster networking or DNS configuration issue.
3.  **Authentication Failure:** The registry is private, and the cluster lacks the necessary credentials (ImagePullSecret) to authenticate the pull request.
4.  **Resource Constraints:** The node is unable to pull the image due to insufficient network bandwidth or storage capacity (less common, but possible).

## Prerequisites
*   **Access:** `kubectl` access with `get`, `describe`, and `edit` permissions on the affected namespace.
*   **Tools:** Access to the cluster's DNS configuration (if diagnosing a cluster-wide issue).
*   **Knowledge:** Understanding of the correct image path (`registry.host/repository:tag`).

## Step-by-Step Resolution

### Step 1: Triage (Initial Assessment)
1.  **Check Pod Status:** Run `kubectl get pods -n <namespace>` to confirm the pod is in `ImagePullBackOff`.
2.  **Gather Details:** Run `kubectl describe pod <pod-name> -n <namespace>`.
3.  **Analyze Events:** Focus exclusively on the `Events` section of the `describe` output. Identify the exact error message (e.g., `no such host`, `unauthorized`, `manifest unknown`).

### Step 2: Identify Root Cause
Based on the error message from Step 1, determine the root cause:

*   **If the error is `no such host` or DNS failure:** The issue is network-related. Verify the registry host name is correct and accessible from the worker nodes.
*   **If the error is `unauthorized` or `ImagePullSecret` related:** The issue is authentication. Credentials are missing or expired.
*   **If the error is `manifest unknown` or `repository not found`:** The issue is the image reference. The image name or tag is incorrect.

### Step 3: Apply Fix
Execute the fix based on the identified root cause:

**A. Fix: Incorrect Image Reference (Typo/Bad Tag)**
1.  Use `kubectl edit deployment <deployment-name> -n <namespace>`.
2.  Locate the `spec.template.spec.containers[].image` field.
3.  Correct the image path to the fully qualified, correct registry/image:tag.
    *Example:* Change `nonexistent-registry.io/fake-app:v99.0` to `my-correct-registry.com/app-name:latest`.
4.  Save and exit the editor. Kubernetes will automatically trigger a rolling update.

**B. Fix: Authentication Failure (Private Registry)**
1.  Create or update the ImagePullSecret containing the registry credentials:
    ```bash
    kubectl create secret docker-registry <secret-name> \
      --docker-server=<registry-host> \
      --docker-username=<username> \
      --docker-password=<password> \
      --namespace=<namespace>
    ```
2.  Update the Deployment YAML to reference the secret:
    ```yaml
    spec:
      template:
        spec:
          imagePullSecrets:
          - name: <secret-name>
    ```
3.  Apply the updated YAML.

**C. Fix: Network/DNS Failure (Cluster-wide)**
1.  If the registry host is correct but DNS fails, escalate to the Platform/Networking team.
2.  Verify that the cluster's CoreDNS/kube-dns configuration includes the necessary records for the registry host.

### Step 4: Verify Resolution
1.  Monitor the pod status: `kubectl get pods -n <namespace>` (Wait for status to change to `Running`).
2.  Check logs for successful startup: `kubectl logs <pod-name> -n <namespace>`.
3.  Confirm the application is functioning correctly via smoke tests or service mesh monitoring.

## Rollback Procedure
If the fix (especially changing the image reference or secret) causes the pod to fail again:

1.  **If changing the image:** Revert the Deployment YAML to the last known good image tag/reference.
2.  **If changing the secret:** Delete the newly created or modified `ImagePullSecret` and redeploy the application using the previous configuration.
3.  **If the issue is network-related:** Do not roll back the application; instead, revert the change that triggered the network issue (e.g., reverting a change to the cluster's DNS configuration).

## Prevention
**Configuration best practices:**
*   **Use Helm/GitOps:** Manage all application deployments via GitOps tools (ArgoCD, Flux) to ensure version control and auditable rollbacks.
*   **Image Tagging:** Never use `:latest` in production. Always use immutable, semantic version tags (e.g., `v1.2.3`).
*   **Secrets Management:** Use dedicated secret management tools (Vault, AWS Secrets Manager) integrated with Kubernetes rather than storing credentials directly in YAML.

**Resource limits and requests guidance:**
*   While not directly related to image pulling, always define `resources.requests` and `resources.limits` for all containers to prevent resource starvation that could mask underlying network issues.

**Monitoring and alerting recommendations:**
*   Implement custom metrics tracking the rate of `ImagePullBackOff` events.
*   Set up alerts that trigger on DNS resolution failures originating from the worker nodes.

## Escalation
| Condition | Severity | Action | Escalation Target |
| :--- | :--- | :--- | :--- |
| DNS failure for a known, correct registry host. | CRITICAL | Immediate investigation of cluster networking components. | Platform/Networking Team |
| Authentication failure after confirming correct credentials. | HIGH | Review cluster RBAC and ServiceAccount permissions. | Security/Platform Team |
| Failure to resolve the root cause after following all steps. | HIGH | Engage senior architectural review. | Lead SRE / DevOps Architect |

## References
*   [Kubernetes Documentation: ImagePullBackOff](https://kubernetes.io/docs/tasks/configure-pod-container/image-pull-backoff/)
*   [Kubernetes Documentation: ImagePullSecrets](https://kubernetes.io/docs/tasks/configure-pod-container/image-pull-secrets/)
*   [Kubernetes Documentation: Pod Statuses](https://kubernetes.io/docs/concepts/workloads/pods/)