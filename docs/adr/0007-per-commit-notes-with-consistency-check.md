# 逐 commit 版本修改说明 + 一致性校验

版本报告要求无论是否有正提升都给出完整修改说明，且正提升提交红色、其余黑色显示。颜色落在「提交」上，因此说明必须是逐 commit 结构：LLM 输出 `commit_notes: [{sha, summary, positive}]`，替代原先只有正提升版本才有内容的报告形态。

**考虑过的方案**：① 版本级一段总结文字 + 正提升条目反推 commit（无法逐条着色，被否）；② 逐 commit 标注（采用）。

**一致性校验**：`has_positive` 必须等于「commit_notes 中是否存在 positive=true」，`positive_items` 非空必须当且仅当 `has_positive=true`；违反按分析失败处理（analyzed 保持 0，下次执行补分析重试）。备选是后端覆写 `has_positive` 为派生值，但那会悄悄改掉 LLM 结论，且堵不住 positive_items 与 has_positive 打架，被否。条件 help-diff 仍只看 `has_positive`（ADR-0003 不变）。

**后果**：旧版本无 commit_notes，通过一次性将 analyzed 置 0 走既有补分析路径回填（LLM 重跑，positive_items 等一并刷新）；回填期间任务执行时间变长。LLM 漏标/错标 sha 不校验，前端按 sha 匹配降级显示（无 note 的 commit 黑色无解释，孤儿 note 丢弃）。`commit_notes` 列的 schema 变更不走手动 ALTER：`database.init_db()` 后由 `_ensure_columns()` 幂等检测缺列并 `ALTER TABLE ADD COLUMN`（可空列，免手工、可重复执行），取代 spec 原「schema 变更手动执行」约定（2026-10-12 code-review 后回填）。
