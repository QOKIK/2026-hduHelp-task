# Campus Lost-and-Found

The system connects campus users who report missing items with users who find items, helping them discover relevant posts and coordinate returning property.

## Language

**User**: A person with a local account on the platform. The current account uses a username and local password; a student number is stored as the planned identifier for future campus unified authentication, but the current system does not connect to that service and does not verify the number.

**Student number**: A required, unique account attribute intended as the identifier for future campus unified authentication. It is visible to the user and administrators, not to other users; it is not currently verified by a school service.

**Lost report**: A post created by someone who has lost an item and is asking others to help locate it.

**Found notice**: A post created by someone who found an item and is trying to return it to its owner.

**Private verification detail**: An optional, non-public characteristic supplied by the author of a found notice to help verify a claim. A related claim request may include a private answer; the author sees both, while other access follows the existing claim-request rules.

**Claim request**: A private request sent in response to a found notice by someone who believes the item belongs to them.

**Lead**: Information sent in response to a lost report by someone who may know where the item is or who has it.

Lost reports and found notices share basic item, location, event-time, and description information. Their type identifies whether the author lost or found the item.

**Similar-post recommendation**: A rule-ranked suggestion between a public, approved, current lost report and found notice, based on their shared item details.

**Lost report status**: A lost report moves through `寻找中` (the owner is still looking), `已找回` (the item has been recovered), and `已结束` (the report is closed).

**Found notice status**: A found notice moves through `待认领` (the owner has not yet been identified), `已归还` (the item has been returned), and `已结束` (the notice is closed).

The post author may directly change a lost report to `已找回` or a found notice to `已归还` or `已结束`. Closing a post also closes its outstanding requests.

**Post freshness status**: Whether an unresolved post has been confirmed as still valid within the last 30 days. `待确认` is independent of lifecycle and moderation statuses and does not itself hide a post from public browsing.

**Post revision**: A proposed material edit to an approved public post. The existing approved version remains public until the revision is approved, when the new version replaces it. A newer edit replaces the single pending revision.

**Claim or lead request status**: A request moves through `待处理`, `已接受`, `已拒绝`, or `已撤回`. A request includes a contact method for offline coordination; the post author can see it, and it is used for offline contact after acceptance. Accepting one request resolves the related post and closes its other outstanding requests. The first version has no in-app chat.

**Post moderation status**: A post is `待审核`, `已通过`, or `已驳回` independently of its lost/found lifecycle status. New posts must be approved before public display; material edits are reviewed again. While an edit is under review, the approved version remains public and is replaced only after the edit is approved.

**Administrator**: An authorized platform user who uses the management area to review public posts and moderate the platform. Private claims and leads are visible to administrators only when a participant reports them.

**Abuse report**: A logged-in user's report about a public post or claim/lead request, submitted for administrator review. An administrator may dismiss the report, take down a post, or remove a request; the first version does not ban user accounts.

**Post removal**: A post without related requests or reports may be deleted. A post with related records is withdrawn from public view while its handling history is retained.

**Status notice**: Users see review and request outcomes in their post/request views. The first version sends no email, SMS, or push notification.

## Current implementation

The stack is Vue 3/TypeScript/Vite with a Go/Gin API and PostgreSQL. The API uses local accounts, Argon2id password hashes, short-lived in-memory access JWTs, and rotating refresh JWTs in HttpOnly cookies. Docker Compose starts the API and database; Vite runs on the host. SQLite data is not migrated or read. PostgreSQL-backed API integration and the browser journey passed locally; the legacy FastAPI implementation and dependencies were removed after those acceptance checks.
