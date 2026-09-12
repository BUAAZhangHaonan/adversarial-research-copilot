# 固定材料质量对照

快照时间：2026-09-07T18:59:04.053746+00:00。

自动评价仅作初步审查，不是专家 gold label、实验证明，也不能据此宣称 ARC 质量优于直接调用 Pro。

2026-09-08 用户追加授权可自主分配账户剩余 228 元。沿用唯一父账本 `arc-vnext-validation-20260907`，授权基线历史花费上界 57.562384 元，加上新增可用 228 元，对应父级总限额 285.562384 元。当前账本实际限额 285.562384 元；历史花费未重置。

父账本全部开发及验证累计已结算 84.810721–84.960337 元，预留 0.000000 元。各组下表只列对应候选及评价账户费用，不能重复加总原 discover 材料费用。

三组沿用各自冻结来源、证据和边界，候选生成及匿名评价禁止在线补证。旧失败、纠错和续跑费用均保留；各系统角色数和实际消耗不同，因此不是严格等成本对照。在线检索能力由独立真实任务 trace 检查。来源记录数不等同独立论文数。

旧分割组 ARC 的 `frozen_material_blocked` 已回查：最初 FRAME 输出为空字符串，结构纠正不能凭空恢复研究判断，因此返回 blocked。这不能解释为已证明冻结论文材料不足。显式新 FRAME 任务保留旧空响应与 blocked 记录；已完成的科学候选不因质量不佳而重新抽取。

本轮只对技术失败/明确 blocked 步骤创建显式任务版本；旧 prompt bundle 保留，新任务携带原材料、原响应与结构化错误反馈。留出主题不用于调提示词。

## 完成情况与自动偏好

| 主题 | 状态 | 自动偏好 |
|---|---|---|
| 合成到真实视觉泛化：区分材质/光照与几何变化 | completed | direct-Pro |
| 拥挤小目标实例分割：区分边界与实例合并错误 | completed | ARC |
| 多模态冲突理解：区分模态可靠性与标签歧义（留出） | completed | direct-Pro |

这三个固定案例支持逐卡审查，不足以证明任一系统普遍占优。

## 合成到真实视觉泛化：区分材质/光照与几何变化

状态：**completed**；冻结 152 条来源记录、19 条证据。

| 方案 | 当前状态 | 卡版本 | 正式 selection | 账户限额/元 | 已结算下界–上界/元 | 停止原因 |
|---|---|---|---|---:|---:|---|
| ARC | COMPLETED | card_5f6fee2f3ac345ae8a44fdb12dcdc8cb v1 | MAIN_REPORT | 285.562384 | 3.158372–3.158377 | frozen_material_comparison |
| direct-Pro | COMPLETED | card_88df573d6fa947b18310c14aa0a369c4 v1 | MAIN_REPORT | 285.562384 | 3.799029–3.799034 | frozen_material_comparison |

匿名评价状态：COMPLETED；已结算 0.672039–0.672039 元。

以下是独立评价会话的自动判断；身份映射只在评价结束后的报告中显示。

**candidate_1（direct-Pro）**

- 问题锚点与反范围清晰：固定 T-LESS test 分割、仅 RGB 合成训练、CosyPose 单视角、BOP-D 分层，未改写为更简单问题；ITODD 许可问题被排除在范围外。
- 最简判别设计与正控制成立：2×2 四单元（含 G-off/A-off 基线）给出可计算的 ΔA、ΔG 与交互项，等预算、同架构、同种子与 bootstrap 敏感性前置能区分归因与实现失败。
- 证据引用准确：PNDR Scene10 的 22.24/37.35/40.44 以及『内容不变、仅光照差异』的条件被正确转述；BlenderProc 双轴默认联合随机与逐轴开关待验证被正确限定。
- 测量缺陷处理到位：把 BOP-D 可见性/歧义分层设为必要组件，并规定不可用时只做替代分层且不宣称消除歧义。
- 资源与不确定性透明：2×3090、4×4K 图、60-160 GPU-h 为有依据外推，并以渲染、训练、测量三个正控制作为继续归因的门。
- 不足一：G-off 的 bop_scene_replication 等于训练在真实测试位姿/相机上，测试几何泄露未单独列入 confounds；首个 outcome interpretation 的『预算优先外观轴』若不加上『已知测试几何』条件会过度推广。
- 不足二：comp_c6 称与覆盖范围相关的交互可由固定宽度 2×2 测量，措辞过强；需按卡自身的 validity_limit 在交互显著时追加单轴收窄/拓宽。

**candidate_2（ARC）**

- 轴定义与混同来源对应好：渲染参数层两轴独立开关直接回应 BlenderProc 默认双轴联合随机与现有消融的非正交性，无像素层后处理式分离的偷换。
- 覆盖梯度的机制增量真实：A/A_low、B/B_low 把缺失类型与覆盖不足分开，并用 Tobin 覆盖原则作为依据；这比单点 2×2 更接近覆盖依赖解释。
- 泄露与有效性边界处理优于同类卡：A 的 scene replication 被标为有意上界，结论限定在已知测试几何；无纹理件的图像形成耦合被用作候选解释而非已证结论。
- 歧义度量处理严谨：BOP-D 重标注公开状态未确认、VSD 在新任务中省略且需深度，卡未在没有这些条件时假装归因读数无歧义。
- 严重引用缺陷：closest_work_delta 把 PNDR Ours-1088 的 40.44 标成『光追40.44』，与提供的表不一致（RayTraced-4352=37.35），把神经渲染结果误归为光追。
- 交互可识别性缺口：Δinter 公式需要 baseline_error，但主干预列表只有 A/A_low、B/B_low、C，资源中未随机化参考为『可选』；按当前最小协议，假设 (c) 不能被正式检验。
- C 与 A/B 的同源性未强制：C 可复用官方 50K 图会引入渲染器/资产代差，尽管正控制要求自生成 C 复现官方行为；主协议应明确统一自生成。
- 类型与规模校准不足：primary_type 标为 new_mechanism 高于目前证据支持的增量（协议与边界判别），且 8 GPU、20K-50K/变体在已注册证据下更像大实现而非最简判别。

**自动评价指出的关键错误**

- candidate_2：closest_work_delta 将 PNDR Ours-1088=40.44 误写为『光追40.44』，与证据 ev_27f77e1a159bf71ca22f4abfbf8689a5 的表头矛盾（RayTraced-4352=37.35）；这会把神经渲染结论错误归属于光追方法。
- candidate_2：交互假设 (c) 需要未随机化 baseline_error，但主最小干预未包含该单元且资源将其标为可选，导致 (c) 在该协议下不可识别。
- candidate_1：G-off/A-on 训练于被复制的真实测试位姿/相机，测试几何泄露未列入 confounds，outcome interpretation 的部署预算建议缺『已知测试几何』限定，存在越界外推风险。
- candidate_1：comp_c6 声称固定宽度 2×2 即可测量覆盖依赖交互，但仅能测当前宽度下的交互；需按后续 validity_limit 追加收窄/拓宽，否则该假设表述过强。

**有依据的优点**

- 两卡均只使用已注册证据，未伪造引用或性能数字；对 PNDR、T-LESS、BlenderProc、BOP-D 的引用条件与限制总体如实（除上述 candidate_2 的 PNDR 归属错误）。
- 两卡均未预设优势假设，给出互斥预测、正控制与 reopen conditions，且把实现失败与零结果区分开，符合开发评估的诚实报告要求。
- 两卡均将 BOP-D 歧义/可见性分层和渲染器开关验证作为归因前提，避免把标注歧义误读为轴效应。
- candidate_1 的 2×2 完整因子设计与等预算控制是最小可判别协议；candidate_2 的覆盖梯度与泄露限定是值得吸收的增强，但不足以覆盖其基线与引用问题。

**仍需核验**

- BlenderProc 目标版本上 A/G 双开关能否真正独立关闭（ev_0a4f606844e5985713ba9d220d4833c9、ev_5b7261fc7da59f73238eb2e7bc12a7de）——两卡均自我标明需代码试点，当前只有模块清单级证据。
- T-LESS 20 个测试场景的逐图布局、光照稳定性与 38K/39K 口径差需按发布版说明核对（ev_93f14f764bfbe67ec9c8da31f4718bb7、ev_60fff8546c130dd02fd5c5f711ad096c）；这决定 G-off/bop_scene_replication 的固定锚点定义。
- BOP-D 的 T-LESS 重标注与代码公开可用性未核验（ev_b71382f95060831b82f107efcb72e638 仅说将公开）；若不可用，两卡只能依赖替代可见性分层，不能完全等价于 BOP-D。
- CosyPose 在候选数据量下能否达到正控制有效性能无实测吞吐证据；候选资源区间为大范围外推，需要预实验闭合。
- candidate_2 如果把未随机化基线设为主干单元，资源与种子计划需重估；candidate_1 需在结论层补测试几何泄露与追试承诺。
- 检索空白只是已核验记录内未发现，不是全局不存在；若定向检索出现同型固定工业场景双轴正交研究，两卡的 novelty 与贡献声明都需降级。

自动偏好：candidate_1（direct-Pro）。

不确定性：两者在同一证据集上共享核心知识空白，证据层几乎等价；偏好的依据是协议的可识别性、最小规模与引用准确性，而不是已有实验结论。两个卡都尚未运行，关键前提（代码开关、正控制、BOP-D 可用性或替代方案）未满足时不能直接推进。最终若 candidate_1 实施，必须并入 candidate_2 的泄露限定与交互显著后的覆盖追试；若 candidate_2 修复基线与引用问题，其覆盖梯度版本也可成为同等候选。。

使用范围：这些结果支持审阅候选论证、引用及最小检验设计；不能替代原文复核、人的科学判断或真实实验。

保留历史失败任务 3 个；原 TaskRecord 与响应路径收录于私有 `work/l4-closeout-export.json`，失败记录未改成成功。

原始结果：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/comparison.json`。

收尾前结果已保留：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/comparison.before-20260908-closeout.json`。

## 拥挤小目标实例分割：区分边界与实例合并错误

状态：**completed**；冻结 276 条来源记录、18 条证据。

| 方案 | 当前状态 | 卡版本 | 正式 selection | 账户限额/元 | 已结算下界–上界/元 | 停止原因 |
|---|---|---|---|---:|---:|---|
| ARC | COMPLETED | card_409fc26111aa439f945b9c4f270250af v1 | MAIN_REPORT | 285.562384 | 7.125499–7.125507 | frozen_material_comparison |
| direct-Pro | COMPLETED | card_a60e80855eac4817b2669445a9a6f934 v1 | MAIN_REPORT | 285.562384 | 7.101934–7.101937 | frozen_material_comparison |

匿名评价状态：COMPLETED；已结算 1.213653–1.213653 元。

以下是独立评价会话的自动判断；身份映射只在评价结束后的报告中显示。

**candidate_1（direct-Pro）**

- 问题锚定与原主题高度一致：卡内定义将边界错误限定为保持实例对应关系的 1–2 px 腐蚀/膨胀或轮廓位移，合并错误限定为相邻实例并集，未替换研究对象；相应定义引用 ev_2a、ev_82、ev_265 作为操作化依据。
- PQ 分解与小目标敏感性的理论基础被引用正确：ev_450 表明 FP/FN 与周界相关而 TP 与面积相关，ev_d7 表明 PQ=RQ×SQ 会把实例级与边界级错误乘在一起。
- 最近工作缺口定位准确且证据可核：Boundary IoU 误差清单不含合并/拆分（ev_2a）；MMA 的 LIVECell 渐进损坏含碎片化/成团，但基线指标无 Boundary IoU/AP 且无面积/δ 分层（ev_a1c）；标签噪声基准无实例合并/拆分（ev_a053）；QuBER 仅将边界细化与实例级修正分工作为出发点而非结论（ev_5dc）。
- 小目标上 Boundary IoU 退化命题有原文支持（ev_63 表明小对象上可接近/等价 Mask IoU），并与 MoNuSAC 单像素修改（ev_265）及 2× 下采样放大效应（ev_82）共同构成可检验条件命题。
- 最小测试具备判别性：冻结 GT 上实施边界、合并、组合、零注入四条件；逐对象 Mask IoU/Boundary IoU/PQ 分解/HD/MMA/SoftPQ/对应通道读数；以标注不确定带和阳性对照排除实现故障；预注册响应差阈值与随机种子可防事后挑选度量。
- 资源透明：0 GPU、8–48 CPU h、约 10^4–10^5 mask，并明确未实测吞吐、严重度校准与数据许可不确定性。
- 主要限制：卡内承认合并注入会改动外层边界导致通道不纯；整数像素严重度分级较粗；且未包含固定匹配/聚合伪差异对照与真实多系统排序检验。这些风险未被裁定为决定性问题，因为卡内设置了接触几何分析和相应结果解释，但会削弱其相对候选二的判别完备性。

**candidate_2（ARC）**

- 问题忠实且以条件判定形式扩展：边界族与实例结构/整体重叠/软匹配族在同一注入矩阵比较，实例合并被显式包含，结论按面积×δ×分辨率分区，不替换原问题。
- 最近工作缺口定位有核验依据：Boundary IoU 模板不含合并/拆分（ev_2a）；MMA 的 LIVECell 腐蚀包含碎片化/成团/移除/增检但无边界度量对照，且逐度量分层统计表不在已读副本（ev_a1c、ev_559）。
- 引入 Nature Methods 排行榜证据（ev_f85：0.99 相关仍可改变名次）与 MMA top-1 分歧（ev_559：最高 50%）是正确的强化：仅响应差不等于决策差异，因而固定匹配/聚合协议并测量 pairwise/top-1 分歧是回答'是否需要分开报告'的必要条件。
- 退化命题与不确定带均被做成自变量：引 ev_63 的 Boundary IoU 小对象等价条件，ev_265/ev_82 的 MoNuSAC 分辨率效应，ev_4e 的 NuCLS IoU–HD 解耦，预设 H1/H2/H3 分区与不可分辨区间，不预设任一侧 gain。
- 软匹配工具纳入合理：ev_865 表明 SoftPQ 以双阈和可调惩罚处理欠/过分割，但未与 Boundary IoU/AP 在小目标域对照，正好构成本卡所缺通道。
- 判别力更强：含同一性/等价性控制、匹配协议控制、聚合协议控制、大对象阳性复现和 δ/分辨率分箱；能区分定义性退化、协议伪差与真实通道差异。
- 主要未决项：官方实现逐行核验、MoNuSAC/NuCLS/LIVECell 数据许可与≥3 个真实系统输出尚未确认；卡内已明确若缺失则将排序分歧结论降级为合成条件下结果，且给出先执行 MoNuSAC 两个面积锚点+LIVECell 高密度子集的最小判别版本。

**自动评价指出的关键错误**

未列出；不等于已证明不存在。

**有依据的优点**

- 两方案均为无训练、无学习模块的测量层判别设计，不落入无理由拼接；组件必要性均有书面因果说明。
- 两方案都把未执行实验视为待检验假设而非已证结论，并给出空结果解释；阳性对照和不确定带校准可防止把实现误差读作通道差异。
- candidate_2 的协议伪差异控制与排序分歧统计（ev_f85、ev_559）直接弥补候选一未显式控制匹配/聚合规则变异的不足。
- candidate_1 更简洁地保持对象对应通道与重叠通道的两路设计，并把合并注入的外边界泄漏列为决定性风险，未掩盖混杂。

**仍需核验**

- Boundary IoU/Boundary AP、PQ/AJI/SEG、SoftPQ、MMA 官方实现版本、依赖与数值复算在记录中均未完成；两卡都承认不能以论文数值替代新测量，但本评估无法证实其可复现性。
- MoNuSAC 测试 GT/队伍预测、NuCLS multi-rater 子集、LIVECell 测试标注及 MMA 使用的三模型输出的实际下载、许可与格式尚未核验；candidate_2 的排序分歧部分存在降级风险。
- candidate_2 引用的 MMA 逐度量分层统计表与摘要 50% top-1 分歧的完整出处需原始表/仓库确认；当前仅 ev_559 的摘要与 Table 1 可核，均不超过该范围。
- QCell（ev_da286）的 FNo/TPp 具体数值不可核验且 verification_status=unverified；两卡仅将其用作机制背景，未作为核心结论，但若后续引用其分工证据需先核验原文表格。

自动偏好：candidate_2（ARC）。

不确定性：两候选均未执行实验，本偏好仅依据方案是否能判别自身命题及控制混杂，不构成对任何假设的证实。candidate_2 在匹配/聚合伪差异、排序分歧与 δ/分辨率分区上判别更完备，故若任务要求二选一优先推荐；但应在执行中先完成其最小合成注入子集与官方度量实现核验，不应因为完整协议依赖未确认的真实系统输出而阻塞第一阶段可独立得到的通道响应结论。。

使用范围：这些结果支持审阅候选论证、引用及最小检验设计；不能替代原文复核、人的科学判断或真实实验。

保留历史失败任务 2 个；原 TaskRecord 与响应路径收录于私有 `work/l4-closeout-export.json`，失败记录未改成成功。

原始结果：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover/comparison.json`。

收尾前结果已保留：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover/comparison.before-20260908-closeout.json`。

## 多模态冲突理解：区分模态可靠性与标签歧义（留出）

状态：**completed**；冻结 9 条来源记录、15 条证据。

| 方案 | 当前状态 | 卡版本 | 正式 selection | 账户限额/元 | 已结算下界–上界/元 | 停止原因 |
|---|---|---|---|---:|---:|---|
| ARC | COMPLETED | card_6634c9573ee049008a6cabb8a1967407 v1 | MAIN_REPORT | 285.562384 | 1.474023–1.474030 | frozen_material_comparison |
| direct-Pro | COMPLETED | card_0ccd1e68ea134bcc8764733c77c7ab05 v1 | MAIN_REPORT | 285.562384 | 1.989082–1.989085 | frozen_material_comparison |

匿名评价状态：COMPLETED；已结算 0.302422–0.302423 元。

以下是独立评价会话的自动判断；身份映射只在评价结束后的报告中显示。

**candidate_1（direct-Pro）**

- 问题与条件保真：明确保留图文冲突、封闭式颜色二选一、固定顺序与提示，直接沿用 CLEVR-CONFLICT 已确认的相反模态偏好模型，并引用 2609.00550 的顺序任意性作为固定顺序的动机；这使该方案仍作用于原题“多模态冲突理解中”。
- 最小测试可识别：A×R 全因子中的视觉跟随率斜率与交互（而非跨条件绝对偏好）能分离可靠性主导、歧义混淆和输出层不可分三种解释；同时记录响应概率差/熵，并以无冲突对照、去视觉命名准确率和标注者一致度作操纵检查。若 E3 成立，作为边界结论仍有科学价值。
- 证据使用与边界透明：全文未核验、缓存不完整、前次检索未重跑均写入 conditions/search_limits/risks，未把未发现冒充已确立空白；2603.09095 渲染伪影、A 分箱像素差异等混淆也被列入 confounds_not_yet_ruled_out。
- 可辨识弱点：A 与 R 的分离在“真值层”是构造定义，但模型感知层可能耦合；输出偏好本身是弱读数，纯图命名阳性对照若效应不足，E3 可能是功效不足的假阴性；未给出最小可检测效应量或预注册功效分析。

**candidate_2（ARC）**

- 引文与既有事实基本吻合：对 VLM-UQBench、V²R-Bench、Mixed Signals、2609.00550 等材料的摘要级总结与已核验证据一致，没有发现伪造引用；其对事后 UQ 路径的证据限制把握准确。
- 决定性偏离：problem_anchor.anti_scope 明确禁止文本—图像跨模态冲突，并把研究问题改为无冲突单句可验证视觉任务中两条梯度能否独立构造。这移除了原题“多模态冲突理解中”的核心条件，属于范围替换而非在原锚内修改方法；方案即使成功，也只能回答一个前置的、更易的构造问题，不能确立冲突情境下可靠性与歧义的区分。
- 内部构造存在标识问题：歧义臂通过“改变目标问句内容”制造分歧度梯度，这会同时改变问题难度、所需线索和真值结构，而不是在同一目标问句上操纵标注歧义；因此“同一固定内容、同一可验证单句任务”的因子化主张可能不成立。
- decision_changed 的概括过强：声称协议失败会使“现有全部基于事后 UQ 或忽略标注者分歧率的逐模态鲁棒性结论都需被重新限定”，但其最小测试仅覆盖自选合成内容、一个标注平台和 2–3 个开放模型，且其 outcome validity_limit 也承认该边界；这一全局性结论未得到设计支持。

**自动评价指出的关键错误**

- candidate_2 将问题从“跨模态冲突中区分模态可靠性与标签歧义”改为“无冲突可验证视觉任务中两轴能否独立构造”，并在 anti_scope 中明确排除冲突与偏好判据；这未保留原题的核心条件，导致其最小实验不能回答本卡问题。
- candidate_2 的歧义臂通过改变目标问句内容来产生标注者分歧梯度，这与“同一目标问句、同一可验证任务”的因子化分离要求冲突，可能把歧义与题目难度/任务结构变化混在一起。

**有依据的优点**

- 两个候选都明确区分了观察、作者表述、自身推断与未核验边界，没有把摘要级缺席或检索失败写成已确立的文献空白。
- candidate_1 在冲突设定内提供了可执行的 A×R 因子设计、正/负对照和三种结果解释；其主报告价值不依赖某个正面预测成立，E3 也构成有效边界结论。
- candidate_2 的“程序化真值不变性检查 + 真实标注者分歧率”测量思路比事后 UQ 或偏好读数更严格，对 VLM-UQBench 显示的现成分数失效问题回应准确；若重新锚定为独立的构造测量问题，可作为单独的潜在贡献。

**仍需核验**

- CLEVR-CONFLICT 与 CLASH 全文未核验，无法排除其中已含分级模态可靠性或标注者一致度数据；这直接限制两个候选的 remaining_claim 强度。
- 2509.02805 仅核验缓存前 12,000/17,877 字符，§3.2 之后是否有降质或歧义操纵未知；材料中提到的 CMC-Bench 未注册为可用 source/evidence。
- VLM-UQBench 扰动栈的可用实现未核验；candidate_1 需重新实现或确认开源版本。
- candidate_2 的“改变问题内容型歧义梯度”是否等同于同一任务的标签歧义，需用同一问题模板、固定答案结构重新做构造校验，当前文本无法判定。

自动偏好：candidate_1（direct-Pro）。

不确定性：当前偏好基于原题保真度：candidate_1 仍在冲突设定内回答区分问题，而 candidate_2 已转移到无冲突构造问题。若 CLEVR-CONFLICT/CLASH 全文显示已有等价 A×R 设计，candidate_1 的 new_problem 增量会被显著削弱；但该文献核验缺口不应被当作支持 candidate_2 改变范围的依据。。

使用范围：这些结果支持审阅候选论证、引用及最小检验设计；不能替代原文复核、人的科学判断或真实实验。

保留历史失败任务 1 个；原 TaskRecord 与响应路径收录于私有 `work/l4-closeout-export.json`，失败记录未改成成功。

原始结果：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.materials.conflict_holdout/comparison.json`。

收尾前结果已保留：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.materials.conflict_holdout/comparison.before-20260908-closeout.json`。
