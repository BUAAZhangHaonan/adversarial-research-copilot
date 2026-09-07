# L2 显式开发输入的定向补证复核

日期：2026-09-07。这次补证确实执行了新检索与原文读取；抽查的两条 evidence 都正确绑定到导入卡 v1 的目标 claim 内容。证据关系分别为 `motivates` 和 `unresolved`，没有把来源可定位误写成主假设已得到实验支持。不过，单像素扰动跨 0.5 阈值的表述，以及 SoftPQ 的“孤立对象”条件，仍有范围扩大。

这是一份开发代理的原文核查，不是领域专家判决。输入来自明确标记的软件开发入口验收提案，不是自然 discover 推荐卡。它不能用于声称 ARC 已自然找到好 idea，也不能代替后续修订、issue 处理或 moderator 的实际结果。

## 对象与完成边界

- Run：`arc-vnext-validation-20260907.explicit_input.develop`。
- 导入任务：`…explicit_input.develop.import`，本次只读时为 `ACCEPTED`。
- 补证任务：`…explicit_input.develop.fresh_verification`，为 `ACCEPTED`，subject 指向 `card_b63f6d85554a493a8be684fca084edd6` v1。
- 初次任务快照中 development 为 `RESPONSE_SAVED`、`accepted_result=null`。本审查只评估已经接受的 import 与 fresh_verification，不读取尚未接受的开发候选正文，不等待或预判后续结果。
- 仅读取 g203 隔离目录的 SQLite（`mode=ro`）、保存状态中的公开结果与 tool_trace、对应来源文本；零 API/MCP 调用、零新检索、零远端写入，没有输出私有 reasoning。指纹重算仅调用纯函数，没有创建 Store 或修改数据库。

卡片原始三条 claim 是 hypothesis/definition，来自输入 `src_80db2d8ebd6f42d28079ccf07c746250`，证据数组最初为空。本次选定最影响方案判断的 c1（两族能否作可解释的归属）和 c2（小尺度下不可分风险）。

补证状态文件：

`runs/arc-vnext-validation-20260907.explicit_input.develop/tasks/5bcbc2750ec85790c636bc80cafccd9d27e419aee7f0245fcb73a490da2bf618/states/5ca51056689a407da4b82cd1fd7076ee.json`

本次读取 SHA256：`ef3d96349fabb31e359ec177c410e5401bc30a0e59b8200c8ac17b1efabb2264`。任务 input_hash 为 `071a5b7fe692a62aeb551d86cc8e4e0041b763ac3a11a74cc3c35fe5cd869ba4`。这些路径均相对于远端 `.arc-validation/artifacts/`。

## 确实新增了哪些检索与读取

fresh_verification 的实际 trace 有 **25 条**：search_web 6、read_web 7、read_paper 3、read_record 9。其 `actual_searches` 中的六个 trace ID、原始 query 与 source ID 集合均逐项匹配六条成功搜索，没有把 read/archive 充作新检索。

六个搜索分别涉及接触对象的 merge/boundary 归属、Boundary IoU 的错误类型、SoftPQ、细胞核受控扰动、Metrics Reloaded、以及再次搜索两族比较。这里的“新”指此任务确实发起了相应动作；已登记论文被重新读出不构成新独立论文。

| 来源 | 实际进入本任务的可读文本 | 与角色叙述的差异 |
|---|---|---|
| Boundary IoU | 三次 read_record 覆盖 `[0,24000)`、`[24000,48000)`、`[48000,52265)`，确实读完当前保存全文。 | 先前 read_web 只登记 24k、没有内联正文；随后窗口读取补齐，最终“全读”属实。 |
| Foucart / Sci Rep | 旧 7k 副本 offset=7000 的一次读取返回空；另一次新 read_web 登记 30k 副本，再由 read_record 实际读入 `[7000,30000)`。 | 本次有效新增读取是 23k；结合 import 的前 7k，累计到 30k。没有把空窗口算入原文证据，完整 37,407 字符仍未在该链全部读入。 |
| SoftPQ v2 | read_web 登记完整 26,956 字符；read_record 实际只读 `[0,24000)`。 | “全文26,956字符已读”不准确。未读尾部是参考文献，不影响此次已核对的方法、实验与限制段，但注册完整不等于模型已读取完整。 |
| CC-Metrics | read_web 请求20k、无内联正文；read_record 从已有登记表示实际读到 `[0,24000)`。 | 角色称前20k，实际直接读了24k；仍远少于50,964字符全文，不能扩大否定范围。 |
| Bruhns等 2025 | `[0,24000)`，全文元数据51,250。 | 部分正文，不能概括未读后半。 |
| Metrics Reloaded | `[0,16000)`，全文元数据291,119。 | 角色明确保留未读大部分的限制，没有作全文级否定。 |
| read_paper / PMC | 三次 read_paper 中一次 error、两次 completed 但没有来源正文；PMC只返回63字符访问页面。 | 不能视为论文阅读；这些调用没有支撑本次选定的两条定向证据。 |

选定证据的关键真实读取：Sci Rep `tool_b61ef8f3f296453c966302b5d2aaf6e8` 登记30k，`tool_658dfaefc74b4bc4871901b1d8ee8eaa` 读取23k；SoftPQ `tool_0719fe14e6c445859dbe3d8ca7940df5` 登记全文，`tool_2ef3fef6dd284d76bb699a3406711b4e` 实际读取24k。其余行为均可在上述状态文件的 tool_trace 复查。

## 目标绑定：两个 fingerprint 均准确

核查按当前实现，对目标 Claim 的内容（排除 evidence_ids）重算 SHA256。两条 evidence 的 claim ID、claim_version 与卡 v1 一致，指纹均相等。因此它们确实指向这些假设版本，不是因文本相似而误挂在别的卡片主张上。

| 目标 claim（version=1） | evidence_id | relation | target_claim_fingerprint（重算一致） |
|---|---|---|---|
| `draft_c1_boundary_vs_merge_metric_response` | `ev_7779b4d0954627588e71a8f492a882e1` | `unresolved` | `1240b42631d36108422c3a23344e9ecca582d1db99b3e522c379093cc67bb0b2` |
| `draft_c2_smallscale_indistinguishability_risk` | `ev_7cd485a9bf7ebfb16b3d7f6905ae97e4` | `motivates` | `6d6df3a89799a58f197ee8b0ad3e92a6be72112f76442faeda19ff673303344a` |

两条 evidence 的 locator_status 与 verification_status 都是 `verified`，但这不意味着目标假设得到验证：前者记录原文摘录可核对，relation 才表明它只是动机或仍未解决。fresh 任务的 input evidence_ids 为空，也不表示它没有产生新 evidence；这些输出已另行登记到上述 ID。

将来如果 claim 文本或条件发生变化，即使沿用名字，这次 fingerprint 对照也不能直接替新主张背书。本审查只核对 v1，没有审计未来争点状态转换。

## c2：数值有原文，跨阈值与接触归属仍未直接证明

目标 c2 是“小尺度接触条件下可能不可分；null 结果不能直接否定两类错误有区别”。对应 fresh finding[2] 引用 Sci Rep 的单像素扰动结果：淋巴细胞腐蚀后中位 IoU 0.80、巨噬细胞0.92；下采样后的淋巴细胞为0.64（腐蚀）、0.71（膨胀）。**这些数值与各自操作确有原文支持。** 本轮比 V3 保留了更准确的操作绑定，也没有把数值直接叫成真实噪声的统计下限。

来源：`src_dda04105c95f4c4996a6d62a004cea06`，canonical URL 为 `https://www.nature.com/articles/s41598-023-35605-7`，version=null，保存30,000/37,407字符。它是新登记的截断表示，不能因与此前完整副本 canonical 相同就声称本任务读了整篇。

- 正式摘录：保存文本 L80 `chars:22697:22811`，唯一匹配；对应淋巴/巨噬细胞0.80/0.92。
- 下采样与0.64/0.71：L80 `chars:23570:23917`。原文是在已经下采样的图像上重复单像素操作。
- 多标注者0.45：L76 `chars:20973:21148`，来自 NuCLS 选定单核的跨标注示例，不是上述 MoNuSAC 单像素干预的中位数。

仍需收窄的是 finding[2] 的“即使1像素形态变化也可逼近或跨越0.5匹配阈值”。所列四个中位数均高于0.5，不能单独证明单像素操作造成了跨阈事件或给出其频率。本次核查的文字中，明确低于0.5的示例属于另一组多标注者比较。不能把这两项拼成同一个受控实验的因果结果；这里也没有反断言单像素扰动绝不可能跨阈。

此外，这些证据没有包含“接触小实例的并集合并”与“剂量匹配轮廓扰动”的双族响应试验，不能证明两类响应已经不可分。该 finding 的 conditions 与 support_explanation 明确承认这一点，`relation=motivates` 是恰当范围。它可以支持阈值敏感性值得检查的动机，不能关闭 c2 的经验争点。整段仍标 `origin=original` 时，后半的跨场景归纳应与原文数值区别看待。

可能影响：若后续把此记录当作“c2 已证实”或“已有实测跨阈频率”，会错误提高风险结论的强度。当前接受的 fresh 结果没有作这种目标升级，本审查也不代替后续 issue/moderator 检查。

## c1：SoftPQ 是相关设施，缺口表述应限于已核对条件

目标 c1 是“两族指标在接触小实例上，能对两类受控扰动给出不同且可解释的归属”。fresh finding[3] 为其登记 `relation=unresolved`，明确既不支持也不反驳目标。这个关系与原文可提供的证据范围一致。

来源：`src_e19af33b64d24ef2b861e077bb8c5986`，arXiv `2505.12155` v2。正式摘录是实验基线段：L77 `chars:12786:13017`，唯一匹配。已核查§4.1–4.3的侵蚀、阈值扫描和分裂实验，§5.4的 Cellpose 真实预测比较，以及§6无重叠输出假设。

原文支持：该受控实验确实比较 F1/mAP/IoU/PQ 和 SoftPQ；所读实验没有加入 Boundary IoU/AP，也没有报告本卡要求的接触密度×面积带×剂量配平的两族归属分析。它能说明匹配阈值和软匹配如何影响响应，不能直接回答 c1。

但两处措辞过强：

- “无接触/重叠配置报告”被写成“合成对象为孤立设置”。未报告接触配置不证明对象一定孤立；§6不允许输出掩码重叠，也不等于对象不能相接。应将这一条件保持为未核实，而非拿来排除该工作与目标域的关系。
- “under-segmentation仅以公式处理”需要限定受控并集合并实验。§5.4明确讨论 Cellpose 真实预测中的 splits/merges，不能说整篇只在公式中处理合并。原文未提供本卡特定受控对照，与原文从未观察真实合并，是不同判断。

§4.3还把每对象分裂成多片与“保持1:1对应”放在一起。finding 照录的是作者措辞，不是本审查验证过的匹配实现；不能据此跳过后续对匹配操作的定义核查。相关定位：§4.3 起点 L85 `chars:14974`；§5.4 起点 L96 `chars:18403`；§6 起点 L103 `chars:20651`。

可能影响：把未知接触配置改成确定孤立，会夸大与近邻工作的条件差距。当前 `unresolved` 避免了直接给 c1 加支持票，但角色汇总中“经验空白无需收缩”仍须受这些未核实条件及其他未读文献约束。本次不重作 novelty 判断，也不声称剩余空白已被覆盖。

## 复核记录与剩余争点

| 来源 | 已保存 content_path | 已核对 SHA256 |
|---|---|---|
| Sci Rep 截断表示 | `sources/src_dda04105c95f4c4996a6d62a004cea06/36a03b926cd0fd9223b08ff05348915110750b5c0eba3f99208a8bbf736ef158.txt` | `36a03b926cd0fd9223b08ff05348915110750b5c0eba3f99208a8bbf736ef158` |
| SoftPQ v2 | `sources/src_97a09004f9fc408b988aee9fa73755fe/6ccd782c8e8b01ca7c6d8b864c49df8d922780f52f16f81e8e2081b0da46d4f6.txt` | `6ccd782c8e8b01ca7c6d8b864c49df8d922780f52f16f81e8e2081b0da46d4f6` |

验证完成：两个来源哈希一致、两个摘录唯一且坐标匹配、两个目标版本/指纹一致、六次实际搜索与声明一一匹配。这里的字符位置是 Python Unicode 索引、零起点、右端不含，行号不是论文页码。

这两条证据可作为后续补证和争点归属的基础：c1 的实测归属能力仍 unresolved；c2 的动机增强，但跨阈事件与接触域外推没有直接试验证据。没有执行任何实验，没有更改 claim 状态，也没有把 `HANDOFF_EXPERIMENT` 建议等同科研通过。

本审查未覆盖 fresh 的其余五条 finding 的全部科学内容，未全面检查新增邻近文献或数据许可，也未读取/判定随后开发修订、issue 转移和 moderator 结果。它们最后是否修正以上问题，必须以各自实际保存的产物另行确认。

## 后续只读快照：card v2 与 round 1 两个角色

主线程随后明确指定复核的新状态：develop 已 `PAUSED_BUDGET`，费用区间为 **4.106986–4.107017 CNY**；round 1 moderator 尚未完成。本次任务快照确认 development、proposer、skeptic 为 `ACCEPTED`，moderator 为 `PENDING`。因此下面记录的是已保存的修订和双方观点，**不是 moderator 科学裁决，也不是 L2 develop 完成**。没有付费调用、提交、同步或研究产物修改。

目标卡仍为 `card_b63f6d85554a493a8be684fca084edd6`，新版本2；其 selection 与 assessment 均为 null。v2标题是“相互接触小实例分割中边界错误与实例合并错误的测量可辨识性与分开处理条件（开发修订v2：最接近文献核查闭合，待最小检验实验交接）”。

### c1/c2：数据库关系没有升级，结构化续版有缺失

本次重新读取两条 evidence：`ev_7779b4d0954627588e71a8f492a882e1` 仍为 c1 version1 的 `unresolved`；`ev_7cd485a9bf7ebfb16b3d7f6905ae97e4` 仍为 c2 version1 的 `motivates`。两者的 target_claim_fingerprint 与上表完全相同，没有被数据库改成 supports 或新的目标版本。

development 的 `evidence_review` 对 c1/c2 均标 claim_version=1、still_applicable=true，并在解释中明确“无实验支持”“不构成验证”；c1 的三条引用包括 SoftPQ unresolved 及两个文献覆盖背景，c2 的引用是 MoNuSAC 动机和 CC-Metrics 接触/阈值伪影。因此 `still_applicable=true` 在这里不等于“假设为真”。

但是，结构化卡片发生了另一种不一致：

- v1 的 `draft.claims` 有三个 hypothesis/definition；v2 的 `draft.claims=[]`。
- 开发角色原始 `response.message.content` 中，`result.proposed_revision` **完全没有 claims 键**；不是角色显式写出空数组。规范化 accepted 结果及保存的 card v2 才出现空数组。
- 同一输出的 `change_summary` 却声称 c1/c2/c3 的“文本与版本不变”，`affected_claims` 列出三者。随后 proposer 的文本仍辩护 c1，skeptic 的两个结构化 criticism.claim_id 仍指向 c2。

这次只能确认“旧目标引用仍在，但当前卡的结构化目标列表丢失”，不能确认它们已经正确续接到 v2。前面的指纹检查只对 v1 有效，不能填补 v2 缺少目标对象的事实。本审查没有人工补 claims、解释为合法撤回，或重新给其绑定证据；实现层处置由另一个审查任务负责。

### Proposer：维持未验证状态，另提出执行规格意见

`round1.proposer.result.claims_defended` 对 c1 仍明确写 SoftPQ “既不支持也不反驳”。它提出固定匹配指标口径、接触定义与数据审计等执行意见，说明交接不构成任何方向的科学批准。没有观察到它把 c1 的 unresolved 证据改成实证支持。

它也承认“接触实例取并集”和轮廓扰动之间难以严格做到像素剂量等价，改用双轴说明。这个文本论证与原问题的操作化有关，不是从 c2 的 motivates 证据中得出的实验验证。proposer 的 `HANDOFF_EXPERIMENT` 仍只是角色建议，不能替代未完成的 moderator 决策。

### Skeptic：提出了实质争点，也产生了新的证据外推

四条 criticism 的 issue_id 均为 null；前三条 severity=material，第四条 minor。这里只沿用角色的 `local_label` 定位，不称它们已经成为数据库中完成裁定的 issues。

1. **`skeptic_merge_dose_contact_confound`**，claim_id 指向旧 c2。它指出合并会改变预测侧接触边界带，因此边界指标对合并也可能有直接几何响应；剂量不对等会妨碍对 H2 的唯一解释。该段是结合定义和 MMA 扰动方式的分析论证，不是 MoNuSAC 证据直接证明的结论。其证据数组包含 `ev_7cd485…`，但正文中的接触带机制没有因此成为该条 empirical finding 的原文事实。
2. **`skeptic_attribution_rule_preregistration`**，也指向旧 c2。它质疑误差归属规则/特征/阈值未固定，引用 c1 的 unresolved 证据 `ev_7779…` 与阈值背景。这是关于实验可解释性的关切，不等于证明 c1 成立或 c2 已发生；现有证据关系仍保持正确。
3. **`skeptic_intervention_half_scope`** 区分受控 GT 底物的测量可分性与真实错误上的分开干预价值。它明确指出测量结论不能直接覆盖后半问题，属于对外推范围的有效提醒；其最终解决仍待后续处理，本审查没有认可其具体补救选项为唯一方案。
4. **`skeptic_smallscale_family_degeneracy`** 产生了明确的新外推：它用 `ev_7cd485a9bf7ebfb16b3d7f6905ae97e4` 的淋巴细胞单像素侵蚀中位 IoU=0.80，推称中位266px核在 d=1 时边界带占比“已接近全掩膜”。该结论不被这项数值支持。

第四项的理由可直接用集合定义核查：在侵蚀预测为 GT 子集的条件下，IoU 是侵蚀后保留面积/原面积。IoU=0.80 对应约80%保留、约20%被该侵蚀操作去掉，不能推出相应边缘带几乎覆盖全部掩膜。具体 Boundary IoU 带宽还取决于轮廓距离与离散形态学定义，不能直接替换；论文报告的面积中位数和 IoU 中位数也不是同一个特定形状的联合几何测量。两方面都不支持该“接近全掩膜”的判断。

可复查原文仍为 `src_dda04105c95f4c4996a6d62a004cea06` L80 `chars:22697:22811`。本次重新核对其30k保存文本 SHA256 与上表一致。原文只报告0.80/0.92，没有该 d=1 覆盖率结论。

因此，**c2 的数据库 relation 没有升级，但 skeptic 在文本论证中把动机性数值扩大成了确定的几何前提**。它据此把最小面积带的族退化称为已知限制，会影响 H2 的解释。尚无 moderator 接受这一前提；这里既不替它降级 issue，也不据此判定整个方案无价值。

### “NucVerse3D 全文子项已关闭”的读取范围不实

proposer 与 skeptic 确有新的原文读取，不是完全依赖搜索片段。但 tool_trace 与 registry 不支持它们联合声称的“全文级闭合”：

| 项目 | 实际保存/读取 |
|---|---|
| 来源 | `src_77cdc484e37a4d069ea1341c174e709a`，EuropePMC fullTextXML；metadata 的 content_total_chars=124,840。 |
| 当前保存内容 | 90,000字符，`content_complete=false`。文件末尾仍在 HD95 定义的 LaTeX 片段中截断，不是文末。 |
| Proposer 可读窗口 | `[0,20000)`、`[20000,44000)`、`[44000,68000)`；另一次 offset60000 的早期读取为空，不能计入。 |
| Skeptic 可读窗口 | `[68000,90000)`，共22,000字符。`more_content=false` 只表示已到登记前缀末端，同一返回的 content_complete 仍为 false。 |
| 两角色联合覆盖 | `[0,90000)`，不是 `[0,124840)`。缺少的34,840字符没有被本次角色链通读。 |

skeptic 的 `resolved_objections` 与 note 把 `[68000,90000)` 称为“至文末”，并将“全文缺口”列为关闭，这个读取范围判断错误。可以保留它对已读 Methods 段的有限观察，不能把未读部分排除为没有相关实验。本审查没有新读取缺失文本，也没有反向声称其中一定存在反例；它只否定“此链已全文核实”的说法。

来源路径：`sources/src_6836e6877fb94b9aaa602213dfeac41b/f240c60bccf7fa15a6bd69ac626949990c65fc86fe87bfb8e9a8c3b566e88b72.txt`；本次重核 SHA256=`f240c60bccf7fa15a6bd69ac626949990c65fc86fe87bfb8e9a8c3b566e88b72`。关键尾段 call_id=`tool_1bd6b847fa0f4fa1a9cfe82958b61f45`。

### 可复查的角色产物

以下路径均相对于同一 `.arc-validation/artifacts/`，只读取公开结果与 trace。

| 角色 | 状态文件路径 | SHA256 |
|---|---|---|
| development | `runs/arc-vnext-validation-20260907.explicit_input.develop/tasks/b6063e58916d697ade0ea41c1ad17d5a179f2d404f7acab76370bf482e861c73/states/59e90ccb74fb42d3a712861d85d59b00.json` | `d26f72b7f7b39c557bbd5415d0048bfebd32b8d6a9ab1131efd780fa7ca9a74a` |
| proposer | `runs/arc-vnext-validation-20260907.explicit_input.develop/tasks/4a05214e1bad7e216d39280d3baa27edcd733606445ee117d9d5442eba1a0f14/states/07aaeea64d80440aa1a3fc66e3c8c27d.json` | `4dab808f639d9ab524ef3f75cbc30809265a6816f3908873a0dccc77939bb2cd` |
| skeptic | `runs/arc-vnext-validation-20260907.explicit_input.develop/tasks/3dc0245403d7e96f2ad9e5b91fd69232f493d47b5e5aa7fc4f2825bc8b8b8f14/states/255c9d18d21b41a08dc625c012dfefe4.json` | `2b441b3adb13ee2553a1a0a38a8eef955efd00601ffeb9887a0945e65a340b40` |

这次看到的有用进展是 proposer/skeptic 能围绕操作化、剂量、归属规则和干预外推提出不同观点；同时仍有结构化 claim 续接缺失、动机证据语义升级和全文读取范围误报。双方建议交接、skeptic 的 surviving_decisive_issues 为空，都不能替代尚未执行的 moderator。预算暂停也不是科学通过或否决。

## 独立 run 入口：空正文重复读取与开发者控制暂停

这一节是另一个入口验收 run：`arc-vnext-validation-20260907.explicit_input.run`，停留在 `.import` 任务。它不同于上文已经形成 v2 的 `explicit_input.develop`，两者费用和完成状态不能混用。

### 循环证据

2026-09-07 06:45:05 UTC 的固定状态快照显示 import 为 `IN_FLIGHT`。已完成工具 trace 共258条，其中 read_record 237、search_web 11、read_web 7、read_paper 3；总体256条 completed、2条 error。11次搜索的 query 各不相同，因此早期确有不同查询；但随后已进入重复读取阶段。

- 最后连续 **215条** 是无正文的 read_record。
- 最近40条正好是同20个来源各读2次，全部参数为 `offset=0, limit=3000`；每条 `access_status=metadata_only`、`content_origin=metadata`、`content_path=null`、正文长度0，却同时有 `content_complete=true`。除调用自己的 trace_id 外，只有20份不同返回。
- 全部237次 read_record 的目标均为 `src_…`，没有读取历史 task/run 对象。最近40条没有新 search/read_web，不是继续扩展文献覆盖，也不是外部服务报错后的自动重试。

最后三条示例：

| call_id | record_id | args / coverage |
|---|---|---|
| `tool_1c412bb9bd524a66bbe1d078cd67dbd1` | `src_e73bae1a9a1f461b9f1a0b9752d18efb` | offset0、limit3000；metadata_only；0正文 |
| `tool_c5d469868a87457890acb259526531cf` | `src_7a1feceb008744f1b704476a72f9f0cc` | offset0、limit3000；metadata_only；0正文 |
| `tool_1cc98384eb464a6eaa0425dffb924873` | `src_20cabd249d3c4b66b593c1dfd5be1189` | offset0、limit3000；metadata_only；0正文 |

固定状态路径：`runs/arc-vnext-validation-20260907.explicit_input.run/tasks/7fa45215f940411069afa06bfb74a546dff464b0f25961b4a40fea0fa96d9454/states/9af411cfd953405fa824c94d0b7dfa90.json`。

另一次紧接着的请求元数据抽样中，最近40个模型请求均为 `deepseek-v4-flash`、`reasoning_effort=max`、thinking enabled、stream=true、max_tokens=384000、5个工具；消息条数从479增至557。这里只读取请求设置和消息数量，没有读取/输出 reasoning。它显示上下文随空读循环持续增长，模型设置没有降级；该记录不能单独解释模型为何重复选择同一动作。

这些数字是暂停前的固定抽样，不是最终调用总数。最终账本的654 calls同时包含模型和工具预留，不能直接与258条工具 trace比较。

### 实际暂停方式与账本结果

**系统没有自动发现并终止循环。** 主线程确认循环后，在开发验收环境针对这一个 run 临时安装数据库准入 trigger，拒绝之后对 `budget_calls` 的新 INSERT。它没有更改账户额度，也没有中断已发送的流式请求。

安装时间为06:48:06 UTC。当时唯一已开始请求 `call_c3532cc771304bff85d163e3aad6cb69` 的 started_at 为06:48:04.563789 UTC。该请求正常完成，finish_reason=`tool_calls`，原始结果完整保存、账本为 `SETTLED`；随后新工具调用的 reserve 在发送前被拒绝。

这次停止最初记录为 run `ERROR` / `IntegrityError`，原始异常保存在维护审计中。收尾后该 run 明确标为：

- status=`PAUSED_PROTOCOL`
- stop_reason=`metadata_source_empty_read_loop_development_pause`
- 账本654 calls，费用 **6.464293–6.464552 CNY**；reserved=0、unknown_calls=0、未结算下界=0；20元子账户剩余13.535448元。

主线程收尾记录确认预算账户与授权哈希未改、无 pending/unknown，进程3178797退出，临时 trigger 已删除。维护审计保存了安装时账户哈希 `7e7d07fb6edd8a4830b9e70becf7b0a9b064f511c710982ce48acd5aa9f55ba4` 与授权哈希 `4614b0e9ccd187f152b2d2ea7bf6181097b8ab9fe88c69a770cd4196ec444bad`。

本次只读复查进一步确认：最终 run 状态及 stop_reason 如上，指定 trigger 数量为0，`/proc/3178797` 不存在，SQLite integrity_check=`ok`、foreign_key_check 0项。没有在此审查中执行 trigger、改状态、补账或终止进程。

对应维护审计：

1. `maintenance/pause-empty-read-validation-20260907.json`：开发专用准入阻断、安装时在途 call、预算哈希与操作边界。
2. `maintenance/pause-empty-read-validation-20260907-close.json`：原始 ERROR/IntegrityError、trigger移除、既有请求完整结算、最终账本与无新增发送的收尾记录。

最后已结算模型响应路径：`runs/arc-vnext-validation-20260907.explicit_input.run/tasks/7fa45215f940411069afa06bfb74a546dff464b0f25961b4a40fea0fa96d9454/states/0720889210c341b4b7391f8fae321e4b.json`。

### 这次结果能证明什么

它证明旧运行在 metadata-only 来源上反复读取零正文，并由开发者在下一次准入处有记录地暂停，已经开始的请求得到保存和结算。它不能证明自动循环检测存在、修订后的工具提示已经阻止循环，或 run 入口已完成。

暂停后的 metadata 正文缺失提示正在离线修订，是否消除该行为须由整合后的独立新案例验证。这次没有把失败入口当作科研拒绝，也没有修改 raw/task/card 或账本来制造完成结果。
