# Study Note Contract

Use this contract when the user wants to learn from a video quickly or decide whether to watch the original.

## Default Output

Write in Chinese by default. Preserve important original terms in parentheses on first use.

1. `一句话结论` - State the core message in one sentence.
2. `是否值得看原片` - Give a practical watch/skip recommendation and who benefits.
3. `3 分钟速读` - Summarize the video in 5-8 bullets. Each factual bullet should include a timestamp when available.
4. `章节地图` - List timestamped sections with a short purpose for each section.
5. `核心概念` - Explain important terms, mechanisms, tradeoffs, or frameworks. Use source timestamps.
6. `例句库` - For language-learning, communication, writing, or phrase-heavy videos, include source-backed examples with timestamps plus clearly labeled practice examples. Skip only when examples are irrelevant to the topic.
7. `可执行要点` - Convert advice into actions, checklist items, or decision rules.
8. `易错点` - Highlight misconceptions, caveats, missing prerequisites, or conditions where advice may not apply.
9. `复习卡片` - Provide 8-12 concise Q/A flashcards.
10. `自测题` - Provide 5 questions with answers hidden after the question list when useful.
11. `来源边界` - State missing context, partial transcript limits, visual-only content gaps, and confidence.

## Compact Output

If the user asks for "quick", "short", "重点即可", or similar, include only:

1. `一句话结论`
2. `是否值得看原片`
3. `核心要点` - 5-8 bullets with timestamps when available.
4. `下一步` - Tell the user what to review, watch, or practice next.
5. `来源边界`

Do not omit `是否值得看原片`, `下一步`, or `来源边界` in compact mode. Those sections distinguish a study digest from an ordinary summary.

## Deep Output

If the user asks for a course note, Obsidian note, exam prep, or deep study, add:

- A dependency graph of concepts when the topic has prerequisites.
- A glossary table with term, meaning, timestamp, and why it matters.
- Practice prompts or exercises.
- Open questions to verify by watching the original or checking external sources.

## Source Discipline

- Ground claims in the transcript. Do not invent examples, tools, speaker claims, or data.
- Attach timestamps to non-obvious claims when timestamps exist.
- Use source metadata (title, uploader, description, tags, chapters, available captions) to orient the answer, but label metadata-backed information separately from transcript-backed claims.
- Do not use the description field as evidence that the video actually covered a point unless the transcript also supports it.
- Mark "视频可能展示了但 transcript 未提供" for visual demonstrations, charts, code, or UI details that are referenced but not visible in the transcript.
- Separate direct takeaways from your inference with phrases such as "我的推断是".
- For generated practice examples, explicitly label them as practice examples rather than source examples.
- If source coverage is partial, say it early and lower confidence.
