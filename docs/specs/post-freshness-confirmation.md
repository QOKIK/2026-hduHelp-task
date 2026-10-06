# 失物信息有效期确认规格

## Problem Statement

寻物启事和拾获公告可能长期没有更新，浏览者无法判断信息是否仍然有效。自动删除或下架会丢失仍有价值的线索，因此需要让作者确认有效性，同时保留原有业务状态与处理记录。

## Solution

一条已审核且尚未结案的信息在首次审核通过或最近一次有效性确认/审核通过的修改满 30 天后，进入独立的 `待确认` 新鲜度状态。它继续出现在公开信息板并显示提示，但不参与相似线索推荐；作者在“我的发布”中看到确认入口。作者确认后重新开始 30 天期限。系统不自动隐藏、关闭或删除信息，也不发送外部通知。

## User Stories

1. As a visitor, I want to know when an unresolved post has not been confirmed for 30 days, so that I can judge whether its information may be stale.
2. As a visitor, I want a `待确认` post to remain available in the public board with a clear label, so that potentially useful information is not silently hidden.
3. As a poster, I want a reminder in my own-posts view when an active post needs confirmation, so that I can renew useful information while managing my posts.
4. As a poster, I want to confirm that a post is still valid and restart its 30-day period, so that current information leaves the `待确认` state.
5. As a poster, I want an approved material edit to restart the period, so that a recently reviewed update counts as a fresh confirmation.
6. As a poster, I want a pending edit not to reset the period, so that an unapproved change does not make stale public information appear confirmed.
7. As a poster, I want normal views, searches, claims, leads, and unrelated status activity not to reset the period, so that freshness reflects an explicit confirmation or approved edit.
8. As a visitor, I want `待确认` posts excluded from similar-post recommendations until reconfirmed, so that recommendations prioritize recently confirmed information.
9. As a user, I want returned, resolved, or ended posts to be excluded from freshness reminders, so that terminal items do not keep asking for action.
10. As a user, I want freshness status to remain separate from `寻找中`, `待认领`, `已找回`, `已归还`, and `已结束`, so that confirming validity does not change the item's lifecycle.
11. As a user, I want all reminders to stay inside the application, so that this feature does not unexpectedly send email, SMS, or push notifications.
12. As a user with an existing approved post, I want its current approval date to start the first 30-day period, so that I do not have to recreate my information.

## Implementation Decisions

- Freshness applies only to approved, public, unresolved posts: lost reports in `寻找中` and found notices in `待认领`. Pending moderation, withdrawn, returned, recovered, and ended posts are not due for confirmation.
- The first period starts at initial approval. A successful author confirmation or approval of a material revision resets it. Submitting a pending revision does not reset it; viewing, claims/leads, and unrelated state changes do not reset it.
- After 30 elapsed days without either reset, set freshness to `待确认`. Keep the post visible and searchable, show the label publicly and the action/reminder in “我的发布”, and exclude it from similar recommendations. Do not change lifecycle or moderation status and do not hide, close, or delete it automatically.
- The author confirmation action clears `待确认` and starts another 30-day period. The action is only available to the author of an active post.
- Track freshness confirmation separately from the public approval timestamp, so a simple confirmation does not make an old post appear newly published in newest-first browsing. An approved material revision may update both its approval time and freshness baseline.
- For existing approved records, use the current approval timestamp as the initial freshness baseline; where it is unavailable, use the post creation timestamp. SQLite migration is not part of this work.
- The reminder is an in-product notice in the author's own-posts view. Do not send email, SMS, or push notifications and do not introduce a notification subscription flow.

## Testing Decisions

- Tests assert externally visible status, listing visibility, author actions, and persisted reset times.
- Extend the existing isolated PostgreSQL API integration seam to cover the 30-day boundary, eligible and terminal statuses, pending versus approved edits, confirmation authorization, persisted timer reset, public badge data, and exclusion from recommendation candidates.
- Extend the browser journey to verify a due post is labeled and remains visible, only its author can confirm it, confirmation clears the reminder, and terminal posts do not show the action.
- Control timestamps in isolated test data to simulate before/at/after 30 days; never wait in real time. Existing PostgreSQL API integration and browser journey tests are the prior art.

## Out of Scope

- Automatic hiding, deletion, lifecycle closure, or moderation of unconfirmed information.
- Email, SMS, push notifications, scheduled reminders outside the application, or user notification preferences.
- Expiration rules for claim requests or leads; their current status and post-resolution behavior remain unchanged.
- Public deployment, production task scheduling, or migration from the old SQLite database.

## Further Notes

- This is a follow-up to the project requirements in GitHub issue #1 and the fourth advancement direction. `待确认` is a freshness concept, not a new post lifecycle value.
- Tracking issue: [#4 失物信息有效期](https://github.com/QOKIK/2026-hduHelp-task/issues/4).
- The 30-day cutoff should use a consistent server-side time basis. Tests should set stored timestamps rather than waiting for the cutoff.
