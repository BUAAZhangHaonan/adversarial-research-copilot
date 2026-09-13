# 同材料的实际改写
以下节选来自交付的三版文本。编辑修订没有新增研究；原报告中的旧认识完整保留在 before/，当前判断以冻结 note 为依据。

## 撤回旧动机后，直接讲当前问题

模型首稿：

> 这个想法把技能对环境的引用拆出来单独维护：物体布局或外观变化后，许多技能失败不是逻辑错了，而是它引用的实体解析不到或解析错了。做法是维护一张持久的「角色→实体」绑定表——角色指技能所需的实体功能位；环境变化后只更新绑定、不重写技能代码，把更新范围从重写降到重绑定，而且更新可回滚。

编辑修订：

> 有些技能保存了对象编号或位置。环境变了，代码的操作逻辑仍然正确，保存的引用却可能找不到对象，或指向错误对象。这个想法把技能要找的对象描述，与当前场景中实际对应的物体分开保存；变化后只更新对应关系，保留技能代码。

[原报告](../../.arc-validation/writing-20260913/replay/discover-first-20260909.sample2/before/ideas/idea_aa0524cde2e742dd985973598795053a.md) · [模型全文](../../.arc-validation/writing-20260913/replay/discover-first-20260909.sample2/after/ideas/idea_aa0524cde2e742dd985973598795053a.md) · [修订全文](../../.arc-validation/writing-20260913/replay/discover-first-20260909.sample2/reviewed/ideas/idea_aa0524cde2e742dd985973598795053a.md)

## 数据路径放下，不再展开一套新方案

模型首稿：

> 这个方向想从真实的多模态咨询日志里学出用户眼里的提问代价：不同提问类型、时机、模态的负担不同，如果能从真实交互里反推出这些隐效用权重，就可以检验「任务成功率最优」与「用户效用最优」的 when-to-ask 是否系统性错位，比如过度提问高负担类别，或漏掉用户其实愿意接受的澄清。

编辑修订：

> 这个方向原本想从真实多模态咨询中估计用户对提问负担的偏好，再比较：只追求任务成功率的提问策略，是否会问得过多，或漏掉用户愿意接受的澄清。

[原报告](../../.arc-validation/writing-20260913/replay/discover-first-20260909.sample1/before/ideas/idea_382bc034c1194b5e9aee5aaa53bb57b3.md) · [模型全文](../../.arc-validation/writing-20260913/replay/discover-first-20260909.sample1/after/ideas/idea_382bc034c1194b5e9aee5aaa53bb57b3.md) · [修订全文](../../.arc-validation/writing-20260913/replay/discover-first-20260909.sample1/reviewed/ideas/idea_382bc034c1194b5e9aee5aaa53bb57b3.md)

## 先解释问题，再介绍有条件的数学关系

模型首稿：

> 失败样本里，模型是“看到了证据却没用”，还是“没提取到证据”？这张卡不给逐样本贴标签，而是改求群体估计：只用行为对照时，“被压制”的占比能识别到什么程度。

编辑修订：

> 同一种回答可能来自两种机制：模型已提取正确视觉证据，但回答受语言中常见答案的倾向（语言先验）影响；或者模型根本没提取到证据，只按语言先验作答。材料构造了两种机制在“有图、无图、编辑图”回答上相同的情形。因此，这些行为对照不能自动给每道题贴出唯一的机制标签。

[原报告](../../.arc-validation/writing-20260913/replay/hallucination-20260910.idea3.develop/before/ideas/idea_47f02e90abab4809aab1ff82eb2a01a3.md) · [模型全文](../../.arc-validation/writing-20260913/replay/hallucination-20260910.idea3.develop/after/ideas/idea_47f02e90abab4809aab1ff82eb2a01a3.md) · [修订全文](../../.arc-validation/writing-20260913/replay/hallucination-20260910.idea3.develop/reviewed/ideas/idea_47f02e90abab4809aab1ff82eb2a01a3.md)

## 把名词串展开成技术动作

模型首稿：

> 很多 VLM 幻觉归因论文靠一个关系型统计量来证明归因有意义：它衡量跨对象是否一致，而不是单点准确率，例如跨模型排序一致（Kendall τ）、归因份额与解码增益的相关 r、单族符号一致。本候选问这些统计量有没有判别增量——在只掌握有限信息时，它能否把真结构与这些信息就能生成的替代品区分开。做法是把可用信息限制在一个预先声明的集合里（类别频率、每个模型的空图或输出偏置边际、标签与随机种子），用由此生成、事前固定、且不按目标反拟合的替代品族去复算，看它原本通过的那套结果能否再现。

编辑修订：

> 有些论文用不同模型的排序是否一致，或错误来源占比与缓解收益是否相关，支持它们的归因。这张卡追问：只知道类别出现频率、模型已有输出偏好等有限信息，能否构造替代结果，重现这些统计关系。如果能，统计量区分机制解释与这些简单替代解释的能力就值得怀疑。

[原报告](../../.arc-validation/writing-20260913/replay/mcp-upgrade-20260912.discover/before/ideas/idea_64fbae0b30de41afb23211070d1aa7c3.md) · [模型全文](../../.arc-validation/writing-20260913/replay/mcp-upgrade-20260912.discover/after/ideas/idea_64fbae0b30de41afb23211070d1aa7c3.md) · [修订全文](../../.arc-validation/writing-20260913/replay/mcp-upgrade-20260912.discover/reviewed/ideas/idea_64fbae0b30de41afb23211070d1aa7c3.md)
