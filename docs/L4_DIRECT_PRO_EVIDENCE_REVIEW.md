# L4 segmentation direct-Pro：有限原文复核

这张候选有可追溯的研究动机，但三处关键推论仍需收窄：把 0.64–0.80 说成跨过 0.5；把 Boundary IoU 的小对象分析说成仅有大对象验证；从合成错误的度量响应推出实际干预应分开。以下是开发代理的有限复核，不是专家认可，不修改候选、证据关系或判断。

## 冻结对象与比较边界

- Source run：`arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover`。
- 对照 run：上述 ID 加 `.comparison.direct-Pro`；候选卡 `card_a60e80855eac4817b2669445a9a6f934` v1。
- 首次读取时 compose/novelty 均为 `ACCEPTED`，selection 为 `PENDING`。同次保存的 `comparison.json` 为 `incomplete`：ARC 为 `PAUSED_EXTERNAL / frozen_material_blocked`，direct-Pro 为 `PAUSED_BUDGET / budget_not_admitted`。后续恢复不在本次冻结判断中。
- ARC 同材料分支未形成可比较的完成候选，因此不能据这次审查排列 ARC/direct-Pro 的质量优劣，也不能把 accepted schema 当作科学通过。
- 全程只读 SQLite `mode=ro` 与已保存原件，没有网络检索、模型/MCP 调用，没有读取或输出私有 reasoning。只新增本地此文档，不向研究模型注入结论。

远端 artifact 根为 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation/artifacts/`。

冻结材料文件 `evaluations/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover/evidence.json`：文件 SHA256 `7b61b97a97cc3ddef45c9bb1ec05ed232654cbac931238fe24fc5f2112847802`；内部 material SHA256 `706a5492a913d4f11357f73c6d45fbef22cf4b7290ec86f4e3cdcc9343e799bd`，重新计算一致。下面三份冻结正文也与其原文 artifact 逐字一致。

| 对象 | artifact 路径（相对上述根） | SHA256 |
|---|---|---|
| compose 状态 | `runs/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro/tasks/7ad2d49fe0340787b3585d5f82416ca8ba7680656b675ff458db9c5d9ccf6f8f/states/53a36839881545a899fcdd9b1ede9a8e.json` | `c4ccae4307919c105b9e91540ac399e2549333879f4d810def2f455558126462` |
| novelty 状态 | `runs/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro/tasks/5eb68915166402f69427afb1ca501d2a1d5a1e5b684ac7bd8ca2768420e03691/states/d83b0a6cac17415aa9b249f490a6ec28.json` | `e6064556bd575005c54bfcfe7f2140efb63c069c969006ea03ff4307d2d793d5` |
| SciRep / PQ 原文，37407 字符 | `sources/src_d0aef6ba027a4b7c91b64b426d0754b0/40a3d8c9d718748f7a5b78b0e9096c3e26cc06c696f648082bda7ae858523b9f.txt` | `40a3d8c9d718748f7a5b78b0e9096c3e26cc06c696f648082bda7ae858523b9f` |
| Boundary IoU 原文，52265 字符 | `sources/src_3ebd2d918fbd44909d9ec620722692f7/659dd1897d3b7d4273a102b83976cbabfabbcf22013e8a5e0cdf5a467631d169.txt` | `659dd1897d3b7d4273a102b83976cbabfabbcf22013e8a5e0cdf5a467631d169` |
| QuBER 原文，40835 字符 | `sources/src_44bacb95677d4522a7ec5f3641f1962b/8e7ca0a2be84fcd75aea1231c1ba5e15bdf371aee8f92b7ff24d015b9e142fd0.txt` | `8e7ca0a2be84fcd75aea1231c1ba5e15bdf371aee8f92b7ff24d015b9e142fd0` |

字符定位使用已保存文本的零基 `[start,end)`；行号为一基。它们不代表 PDF 页码。

## 1. 小对象 IoU 数值不能支持候选所写的阈值跨越

**候选位置：**`motivation.observation_or_deficit` 的第 (i) 点，把单像素修改后的中位 IoU 0.64–0.80 直接写成跨过 PQ 的 0.5 阈值。相关结构化 claim 为 `card_claim_overlap_vs_correspondence_channels`；novelty 继续将其概括为理论与经验支持。

**来源与证据：**`src_d0aef6ba027a4b7c91b64b426d0754b0`；`ev_2655a3f6067439208941925f3eb00e13`、`ev_82e3ef6d52ec95e1fc3f9d4ad73c484c`，另有 `ev_d7a27549438329135aa32fe4e848898f` 支撑漏检与面积低估在综合分中的不同权衡。

原文 `chars:22697:22811` / L80 确实报告 MoNuSAC 单像素腐蚀中位 IoU：淋巴细胞 0.80、巨噬细胞 0.92；`chars:23570:23917` / L80 报告先将图像下采样两倍，再做单像素腐蚀/膨胀，淋巴细胞为 0.64/0.71。这些中位数都大于 0.5。它们既不能证明中位数跨阈值，也不能单独确定个别对象跨阈值的比例。

原文确有 NuCLS 的 0.45：`chars:20700:21350` / L76–77 为一个模糊边界示例的不同专家分割比较。它支持某些专家看来同样合理的轮廓也会无法匹配，但不是 MoNuSAC 单像素形态学处理的同一实验。候选后面的倾向假设段提到 NuCLS 0.45，并不能消除前面混用实验条件的错误。

候选把单像素扰动结果作为严重度参考，同时列出“标注不确定带外推待核”，这部分保留了合理限制。但在最小检验中仍把这些跨设置的中位数称为校准带；它们不是目标子集的重测方差、置信区间或已校准噪声阈值。该区别会影响“响应差超过噪声带”的判定依据。

## 2. Boundary IoU 的条件性等价有依据，未做小对象验证的表述过强

**候选位置：**`card_claim_boundary_iou_small_object_equivalence`，以及 motivation 中“独立边界敏感性的结论只在大对象上验证”；novelty 的最近工作判断沿用了其小对象主要为分析性前提的叙述。

**来源与证据：**`src_a6b97f7d095e450582d4e8217835c31f`；`ev_63d6ce44fbe37f6a0a9cf7cb71c1043d`，精确引文定位 `chars:21674:21940`。

原文 `chars:20400:22550` / L82–89 先定义分别取 GT 与预测各自轮廓内的带，再计算 IoU。带宽大到覆盖两个完整掩码时，与 Mask IoU 等价；较小对象是否接近等价仍取决于带宽。因此候选把它保留为有条件假设、提出 δ 扫描，方向有据。

但候选 claim 的“带宽 δ 与对象面积相当”混用了长度和面积。定义上的精确条件是轮廓带覆盖全部内部像素；对象形状和局部厚度也相关，仅面积分箱不能保证等价。原始登记 evidence 的条件也有这种长度/面积混写，不能因为引用 ID 已验证而继承其科学准确性。

紧接该定义的原文明确用 Figures 6/7 分析不同对象尺寸，并指出小对象上两度量的行为；`chars:26700:28200` / L100–108 还包含 COCO 的 APS 对照表。因此不能说论文只验证了大对象。真正仍可保留的缺口是：这些材料没有证明候选所规定的拥挤小细胞、接触几何、合并注入与多指标共同协议已经完成。把一般小对象分析也说成空白，会夸大剩余新颖性。

## 3. 度量通道响应不等于干预分工已成立

**候选位置：**`card_claim_overlap_vs_correspondence_channels`、`card_claim_quber_intervention_division_unverified`、H1 的不同预测，以及 `minimal_test.outcome_interpretations[0]`。候选明确不训练或比较实际边界细化/实例分离模型，却在第一个结果分支中直接推到“干预也应分开”。

**来源与证据：**SciRep 的 `ev_d7a27549438329135aa32fe4e848898f`（`chars:24153:24498`）支持 PQ 对漏检和面积低估可能给出不适合特定用途的权衡；QuBER 的 `ev_5dc35378204c1306ba2fb4c6644d1043`（`chars:2489:2674` / L7）描述既有细化方法对实例级错误的局限；`ev_e9ae4653122b66fd99bbe33d8ae04ae9`（`chars:3583:3850` / L8）则记录作者用统一误差估计同时处理两种错误的主张。这些能构成待检验的相反动机，不能直接决定目标域需要两套干预。

候选的操作化和预测也需要区分“生成时实例数不变”与“评测时匹配关系不变”。一个直接的定义反例：100 像素的 10×10 GT 方块向内腐蚀 2 像素后是 6×6，IoU=0.36。GT 与预测仍各有一个实例，但按 IoU>0.5 匹配时 TP=0，RQ 从 1 降到 0。该反例落在候选 50–300 像素与 1–2 像素处理范围内；它是集合和匹配定义的计算，不是已执行的研究实验。因而纯边界注入也能改变对象对应通道，不能预设其保持高分，再把不符合这一预测一概解读为新的物理耦合。

即使未来测得两个错误类型具有不同的指标响应，也只证明所选测量和注入条件的可辨别性；还没有比较真实干预的效果、成本、副作用或一种统一方法能否同时修正二者。候选可以输出后续干预选择的假设，不能由这个无模型最小检验确认干预必须分开。候选的 anti_scope 已正确声明不做该实证，但结果解释没有始终保留相同边界。

QuBER 的范围限定还需谨慎：冻结原文 `chars:16092:16542` / L44 写有小于 500 像素掩码过滤；`chars:18150:19100` / L57–59 描述真实 cluttered 场景、平均 3.3–7.5 个对象以及最高 11–20 个对象。过滤阈值和对象计数不直接测量空间密度，也不能把全部场景确认为“稀疏大对象”。它与拥挤小细胞目标域不同是可核对的边界，“稀疏”则不是已经测出的量。

## 可用结论与未完成项

三处问题足以说明 direct-Pro 也会放大冻结 evidence 中的范围错误，尤其会把有据的动机变成更强的测量或干预结论。它同时保留了无需训练、条件分层、有效性对照和局部检索范围等有用约束；本审查没有据此人工改选或否决。

尚未逐条核查全部 MMA、SoftPQ、QCell、CC-Metrics 主张，也未验证资源估计、真实数据可得性或实际实验实现。selection 的后续产物不在本次已冻结审查内。没有可用的同材料 ARC 完成候选和专家评审，本文件不能支持系统质量排名。
