# 认领私密核验规格

## Problem Statement

当前认领申请由申请人填写情况说明和联系方式。拾获者可能缺少可靠方式区分真正失主与误认者；把更多物品细节公开又会降低核验价值。

## Solution

允许拾获公告作者为一条公告填写一项可选的私密物品特征。公告仍公开原有描述；只有设置了私密特征时，认领人提交申请才必须填写对应答案。拾获者根据申请人给出的答案人工核验并沿用现有接受/拒绝流程。

## User Stories

1. As the author of a found notice, I want to record one optional private item characteristic, so that a genuine owner can distinguish their item without publishing every identifying detail.
2. As the author, I want the private characteristic excluded from public cards, detail pages, search, and recommendation results, so that it remains useful for verification.
3. As a claimant, I want to see an answer field only when the found notice has a private characteristic, so that I can provide the requested proof without seeing the secret itself.
4. As a claimant, I want the answer required when the author configured a private characteristic, so that the author can evaluate the claim.
5. As a claimant, I want my answer to remain private and visible to me in my own request, so that it is not exposed to other users.
6. As the found-notice author, I want to see the private characteristic and each related answer with the claim request, so that I can compare them.
7. As the author, I want to accept or reject the claim myself, so that a text answer does not automatically decide ownership.
8. As a claimant, I want existing found notices without a private characteristic to continue using the current claim form, so that existing information remains usable without backfilling.
9. As an author, I want edits to a private characteristic reviewed under the existing post-revision process, so that the approved characteristic stays active until its replacement is approved.
10. As an administrator, I want the existing privacy rule to remain in force, so that private claim content is visible to me only after a participant reports the request.
11. As a platform user, I want verification to use text only in this scope, so that the service does not collect claim photos or identity documents.
12. As a user, I want the existing claim explanation and offline contact method retained, so that this verification detail supplements rather than replaces current coordination.

## Implementation Decisions

- A found notice may have zero or one private verification detail. Lost reports do not use this field.
- When the detail is absent, keep the current claim request flow unchanged. When present, show a separate answer field and require a non-empty answer at both the browser and API boundary.
- The answer is attached to the private claim request, not the public post. The claimant can see their own answer; the found-notice author can see the characteristic and answers for their notice; unrelated users cannot see either. Administrator access continues to follow the current participant-report exception.
- Never include the private characteristic or answer in public list/detail payloads, public search indexes, recommendation explanations, or anonymous responses.
- Treat edits to the private characteristic as part of the post revision. The currently approved characteristic remains effective while an edit is pending; approval replaces it with the rest of the approved revision; rejection leaves it unchanged.
- Existing found notices do not require a private detail. The feature does not change claim status transitions or automatically accept/reject requests.
- Verification uses text only. Do not add image upload, identity-document collection, or automatic/AI verification.

## Testing Decisions

- Tests assert response visibility, request validation, and claim handling through API and browser interfaces.
- Extend the existing isolated PostgreSQL API integration seam to verify that public list/detail/recommendation responses never expose either private field; the author and claimant receive only their permitted fields; unrelated users and administrators without a participant report are denied; a reported request follows the existing disclosure rule; and claim submission enforces the answer condition.
- Verify pending edits preserve the prior approved private detail and that approval/rejection changes the effective detail atomically.
- Extend the browser journey to configure a private detail, submit an answer, confirm the answer is not shown to another account, and let the author accept or reject manually. Also cover a notice with no configured detail and an edited detail awaiting moderation.
- Existing PostgreSQL API integration and browser journey tests are the prior art. Use separate users and isolated database state for each privacy assertion.

## Out of Scope

- Image or file evidence, identity-card/student-number verification, school SSO, and AI ownership scoring.
- A private chat, external notifications, account reputation, or automatic claim decisions.
- Changing the rule that administrators can inspect request content after a participant report.
- Applying private verification details to lost reports or lead requests.

## Further Notes

- This is a follow-up to the project requirements in GitHub issue #1 and the third advancement direction. It preserves the existing claim-request privacy model and approved-revision behavior.
- Tracking issue: [#3 认领私密核验](https://github.com/QOKIK/2026-hduHelp-task/issues/3).
- The current schema and forms store only a claim explanation and contact method; this feature adds a distinct private characteristic/answer concept without changing the public description.
