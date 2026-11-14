# Service integration Goldfish report
Fresh read-only reviewer: /root/service_integration_review. Changed backend checkpoint, separate from R2 layout review.
Initial disposition: changes_requested.
GF-S1: completed probes disappeared (active/recent vs active/jobs), no accessible measurements. Fixed jobs collection plus bounded media-result action and Show measurements.
GF-S2: rapid Dictate clicks could start concurrent polls and duplicate final text. Fixed synchronous guard and generation invalidation.
GF-S3: dictation error object rendered [object Object]. Fixed error.message.
Targeted recheck disposition: no_supported_blocker_found. Confirmed durable unique-job events, restart-persistent acknowledgement, condition-based SSE, no job polling timer, CLI event wait and independent queues.
Limits: reviewer read-only, no execution/listening/mic/provider/native checks. Actual overlap used cached media probe, not proof of parallel heavy computation. External director execution still unconnected. Later imported-result notification reconciliation syntax checked only.
