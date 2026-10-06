# 相似失物线索推荐规格

## Problem Statement

失主和拾获者需要自行搜索、筛选公开信息，即使已有一条内容相关的寻物启事或拾获公告，也可能错过另一侧的信息。用户希望在查看一条信息时看到少量、可解释的跨类型线索。

## Solution

在失物信息详情页展示最多五条相反类型的相似信息。推荐使用简单、可解释的规则匹配物品名称关键词、类别和地点；事件时间只有在能识别为日期时才参与排序。没有匹配信息时不显示推荐区域。

## User Stories

1. As a campus visitor, I want to see related found notices while viewing a lost report, so that I can discover whether someone has found the item.
2. As a campus visitor, I want to see related lost reports while viewing a found notice, so that I can help connect an item with its owner.
3. As a visitor, I want recommendations to include only public, approved, active posts, so that I do not follow unreviewed, resolved, closed, or withdrawn information.
4. As a visitor, I want posts marked `待确认` to stay out of recommendations until their authors confirm them, so that suggested information has a recent validity confirmation.
5. As a visitor, I want the current post author's other posts excluded, so that recommendations point me toward another possible match.
6. As a visitor, I want at most five recommendations ordered by the number and strength of matching details, so that the section stays focused.
7. As a visitor, I want each recommendation to state which details matched, so that I can judge its relevance without treating it as a confirmed match.
8. As a visitor, I want recommendations to use name keywords, normalized category and location, and parseable event dates, so that approximate but related information can still be surfaced.
9. As a visitor, I want no recommendation section when there are no candidates, so that an empty module does not add noise.
10. As a post author, I want recommendations to be read-only and not change either post's status, so that a possible match does not imply a confirmed return.

## Implementation Decisions

- Apply recommendations only on the detail page, for both lost reports and found notices. Do not add a home-page or publish-form recommendation surface in this scope.
- A candidate must be a publicly visible, approved, active post of the opposite type. Active means `寻找中` for a lost report and `待认领` for a found notice. Exclude withdrawn posts, `待确认` posts, the current post, and other posts by the current post's author.
- Rank with deterministic rules using item-name keyword overlap, normalized category and location, and event-time proximity only when the event-time text can be parsed as a date. Stronger and more numerous matching signals rank higher; use newest approved post as a stable tie-breaker.
- Return at most five candidates. Each visible match reason names the field or fields that contributed to the recommendation. A recommendation is not a request, claim, or match confirmation.
- Hide the section when no candidate has a usable matching signal. Recommendation data must contain only fields already allowed in public post details and must never expose private verification details or request information.
- Reuse the current public lost-report/found-notice concepts and their lifecycle and moderation rules. This feature does not change post state.

## Testing Decisions

- Tests assert externally visible API results and browser behavior, not ranking helper internals.
- Extend the existing isolated PostgreSQL API integration seam to cover opposite-type eligibility, approval and lifecycle filters, `待确认` exclusion, author exclusion, the five-result limit, stable ranking, match reasons, and public-field privacy.
- Extend the browser journey so a visitor opens each post type, sees only relevant opposite-type recommendations, can open a recommendation, and sees no section when there are no matches.
- Existing PostgreSQL API integration and browser journey tests are the prior art. Fixtures should control event-time text and approval times instead of relying on current data.

## Out of Scope

- AI, semantic embeddings, image matching, uploaded photos, or externally hosted matching services.
- Recommendations on the home board, during post creation, or in administrator tools.
- Personalized recommendations based on student number, account reputation, contact details, or browsing history.
- Automatically accepting claims, resolving posts, or notifying users that a match is certain.

## Further Notes

- This is a follow-up to the project requirements in GitHub issue #1. The first advancement, homepage motion, is already specified in `homepage-motion.md` and implemented; this spec covers the second advancement direction.
- Tracking issue: [#2 相似线索推荐](https://github.com/QOKIK/2026-hduHelp-task/issues/2).
- The current `event_time` field is free text. Only parseable dates may influence time ranking; opaque time descriptions must not be guessed.
