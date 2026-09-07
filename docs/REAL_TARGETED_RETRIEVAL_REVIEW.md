# 真实定向补证与主张关联核查

这份核查只读g203隔离worktree中的SQLite和已保存文件，未发起模型/MCP请求、未等待或干预driver。主体状态读取时间为2026-09-07 10:09:19.532686 UTC；随后只核对下列固定原件及正文切片。它是过程快照，最终阶段状态以VALIDATION_SNAPSHOT与续跑记录为准。

已确认自然rendering卡有“具体增量主张→新增原文阅读→最近先例覆盖判断→selector采用该判断”的真实链。判断没有因为新增先例而翻转，但理由具体改变。explicit_input_schema_v2.develop也有真实定向原文补读；其fresh_verification在本次观察中未被接受，因此不能把这些动作写成新增EvidenceRecord或争点已解决。

## 自然卡：DIMO先例改变了论证，未翻转覆盖判断

Run为 `arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover`，card为 `card_52bce58017164c2b9594c418eb0cac7b` v1。原始COMPOSE卡的 `claim_d1c_gap_logical@1` 是逻辑主张：在已检范围内，T-LESS固定工业场景的外观轴/几何轴贡献可分性、歧义分层及度量族条件化问题尚未被回答。原卡的最近工作清单包含PNDR、BOP/Hodaň等，但没有DIMO的 `src_bf6cc4ca084d47a4bc92bfbea82c4440`。

| 环节 | 已保存的具体证据 |
|---|---|
| 原主张依据 | COMPOSE原卡 `claim_d1c_gap_logical@1` 引用 `ev_93f14f764bfbe67ec9c8da31f4718bb7`、`ev_18585463168c87fd22712d8c822d2b12`、`ev_266e8b52029f8abee2d857dba5acd402`、`ev_27f77e1a159bf71ca22f4abfbf8689a5`、`ev_b7d339ab3d162d2f246f15c5d43dfd7c`。这些是原调查依据，不能冒充novelty新增登记的证据。 |
| 新原文获取 | draw1.novelty调用 `tool_25461b1a13694218b1b7f6dba01201cd` 读取ar5iv 2211.16066前缀；`tool_7d8f2c18de5f4cc3bba14b470deabed6` 随后将同来源缓存扩展到18000字符。URL为https://ar5iv.labs.arxiv.org/html/2211.16066，source ID为 `src_bf6cc4ca084d47a4bc92bfbea82c4440`。 |
| 实际返回模型的正文 | `tool_651cbfda30b44f989d5b96b001b90187`：offset=0、limit=12000，返回12000字符；`tool_75624b657b7e407890e4bd988d458cc5`：offset=12000、limit=12000，实际返回6000字符。两条content均与对应保存正文切片完全相等。 |
| 原文能直接支撑的局部事实 | 缓存中 `1775` 位于字符15356，等图数比较段位于字符16577附近，`5.22` 位于16874。可核对等量图像与“随机光照+真实位姿”的2D检测结果；这些位置均落在第二次分页实际返回的12000–18000范围。 |
| 新颖性判断 | ACCEPTED的novelty.closest_works[0]明确写 `card_claim=claim_d1c_gap_logical`、`coverage=partial`，解释DIMO有同构的位姿×光照2×2，但其读数为2D检测AP、域非T-LESS，未覆盖卡提出的6D位姿错误分解/歧义分层/度量族问题。overall contribution_coverage为not_covered。 |
| 未翻转及理由改变 | recommended_selection_effect明确维持增量主张，建议补入DIMO/SADGE，并将DIMO的2D结果作为H1/H2参照预测。不能把“维持”解释成没有使用新证据；新增同构先例使理由从既有聚合/单轴工作，变为对直接结构性先例的分条件区分。 |
| 下游采用 | ACCEPTED的draw1.selection为MAIN_REPORT/PROMISING，其closest_work_delta再次明确列出DIMO、1775张、5.22 AP和2D/6D条件差异，并要求下一版卡补入该先例。这证明新材料进入了下游判断；不证明研究价值被人认可或已完成后续develop/run。 |

此处新增的是有实际读取trace的SourceRecord与角色判断依据。DIMO来源在本次SQLite查询中没有EvidenceRecord；novelty.closest_works[0].evidence_ids也为[]。run中19条EvidenceRecord来自既有调查，不能把它们算作此次novelty新登记。该例证明主张层面的实质补查与下游理由关联，不冒称已经完成“新目标EvidenceRecord→issue ledger解决”的闭环；该run的issue表为空。

DIMO保存正文只有18000/34868字符，content_complete=false。上述局部数值与实际阅读成立，但novelty关于整篇工作“没有某分析”的否定判断仍是模型范围判断，本审计没有补读剩余原文，不能把它当作全文不存在的独立证明。选择模型给出PROMISING也不是本审计替它认定PROMISING。

## 明确人工输入develop：补读真实发生，接受与争点解决尚未发生

Run为 `arc-vnext-validation-20260907.explicit_input_schema_v2.develop`。10:09:19 UTC的运行记录为RUNNING、card `card_efc859b4332444d48af5362d8b1a208a` v1、assessment=null，issue数0、该run EvidenceRecord数0。import已ACCEPTED；fresh_verification已保存为PAUSED_PROTOCOL / excerpt_not_in_returned_source，repair_count=0。阶段当时仍在运行，不据该单task状态提前宣布整个阶段最终失败或完成。

import结果明确提出三个待核问题：设计等价的受控边界/合并前例、Boundary IoU是否覆盖相互接触小实例及合并事件、PQ批评文未读余段是否改变小尺度归属判断。对应request_local_id为 `er.closest_work.direct_precedent`、`er.closest_work.boundary_iou_fulltext`、`er.closest_work.pq_critique_fulltext`。这些是导入阶段前置请求，claim_id/issue_id/draw_id均为null，不是已有issue外键。

fresh_verification冻结输入有原卡及其remaining_issues，verification_target为strongest_counterexample_or_unchecked_original_condition，但questions=[]。因此这里只确认后续实际阅读与卡中具体未查原文问题一致，不把它描述成程序已按这三个request_local_id逐一建立可追踪子任务。

| 具体未查问题 | 实际工具动作与覆盖 |
|---|---|
| Boundary IoU正文及附录是否覆盖合并/接触条件 | `tool_b79bf43e79fc468abf97379bf48dfc6f` read_web取得新正文来源 `src_a6b97f7d095e450582d4e8217835c31f`。`tool_20b2e73964d74cbca734ac3d1a22c77b` offset=12000/limit=24000返回24000字符；`tool_2c14e57d874c4fb5a95b30c6f73d580f` offset=36000/limit=20000返回16265字符，实际到52265字符末尾。保存源content_complete=true。 |
| PQ批评文原先未读的论证部分 | `tool_021efc6979d040daa7e8aa301015106b` 对旧缓存offset=9000的读取为空，不能算补证。随后 `tool_052db4bbb2a446539f574f257e505cd8` read_web重新获取Nature正文为 `src_8ad8a14d38214ae18d427bd3ea77cdac`；`tool_f24bd90931a542fda2d9855c11109750` offset=6000返回20000字符，`tool_1fd216da91e543298e3132cf3cf07725` offset=26000返回11407字符，达到37407字符全文末尾。 |

上述四条非空read_record均独立核对：保存正文SHA256与result.content_sha256一致，返回content与相应offset/limit切片逐字相等。不能因为read_web顶层没有content字段而把它误记为空读；这里以实际分页content作直接阅读证据。

fresh_verification原响应含7条候选findings，前两条已将Boundary IoU的方法学先例与本卡接触/合并条件区分，并尝试解释原增量为何保持。但整个候选因excerpt_not_in_returned_source未接受，不能把这些文字计为有效判断改变。前两条Finding的claim_id/claim_version也均为null，不能据此宣布特定claim版本被验证。此次没有moderator/issue transition可证明“争点已经解决”。同SourceRecord可能在其他run存在EvidenceRecord；它们不能借用为这个run新增证据。

## 固定原件与SHA256

以下路径均相对于g203 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation/artifacts/`。文件hash是对实际保存字节计算，正文slice另逐字核对；本审计不改写原件。

| 对象 | 原件路径 | SHA256 |
|---|---|---|
| develop import | runs/arc-vnext-validation-20260907.explicit_input_schema_v2.develop/tasks/049034c13569f140b056383b9ca88afd78b27dcdc8fce68a608187c7b13327d2/states/a2151053542947d2b4b05ee80310cad4.json | 41a7bf8320f55fdfe6daf6c423efedea3f14bf8d87988ceddcba80b622e22c37 |
| develop fresh_verification拒绝原件 | runs/arc-vnext-validation-20260907.explicit_input_schema_v2.develop/tasks/8eb972b2f8894c2d9037502ff66888c474ea6080003c081a9cbc8df231bad5a7/states/8a8d1db7ce494239980efa45dce5f755.json | cfbcb975f64ce9f5d1ed5f60c44f3fea722d60187c2c1ec262d602169b55c708 |
| rendering原COMPOSE | runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/tasks/cf7db35f4d4575ee6a9955f824366a2b1a7d2a39a26602bcc47cdf99a55b8f8e/states/ec6ada6228b34f1bb5a9f532a01cb0ed.json | 30ccf3c668d323bb4df2bd98ef9765b2e32bb1e6c91e802b523f17eb58470ac4 |
| rendering novelty | runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/tasks/7eb096a4b5742be125e67083dc234f228f60c9735e53607da95773c835ef3eb6/states/2703c3e353a7429b81a37b39329677b1.json | 8d343a17f56a5c74bbee5f7d508e082266781791fba074fcc56b21f2edec0b0f |
| rendering selection | runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/tasks/eda010dd42c2c558fa811ba2b98e88f81530027f8e869955f6b56222c5398dc8/states/fc9c14c1cf9b454db3947b406b2689ee.json | 9c2c99a88f03bd7d6046556e66ec2fa50560d89592c0963470390aebf7765b3e |
| DIMO缓存正文 | sources/src_d442df4f790341a7a358f8bfecbc0fb9/a589b81473d5afb851fbec68f9d6c3badf5d2c59ca0e7094b05c71d52bd4e472.txt | a589b81473d5afb851fbec68f9d6c3badf5d2c59ca0e7094b05c71d52bd4e472 |
| Boundary IoU正文 | sources/src_3ebd2d918fbd44909d9ec620722692f7/659dd1897d3b7d4273a102b83976cbabfabbcf22013e8a5e0cdf5a467631d169.txt | 659dd1897d3b7d4273a102b83976cbabfabbcf22013e8a5e0cdf5a467631d169 |
| PQ批评文正文 | sources/src_8ad8a14d38214ae18d427bd3ea77cdac/40a3d8c9d718748f7a5b78b0e9096c3e26cc06c696f648082bda7ae858523b9f.txt | 40a3d8c9d718748f7a5b78b0e9096c3e26cc06c696f648082bda7ae858523b9f |

稳定source ID与正文路径中的目录ID可能不同，因为登记器复用同一表示的已存正文。本次按SourceRecord.content_path读取并验hash，没有由ID相似性推测正文。

任务书验收边界：已有真实“原文补查影响具体主张的覆盖理由，并被selector采用”的例子；本次不能据此勾选独立develop完成、自然同卡L3完成，或声称已观察到带目标claim指纹的新EvidenceRecord解决empirical issue。后两者需对应的最终状态与issue transition原件，而非用工具调用数量补足。

## 后续只读补充：10:19–10:21 UTC的复核与修订停点

这一节补充较晚的保存结果，不回写上文10:09时点。核查仅访问最终回答的content、校验错误、冻结prompt/schema、源记录和卡字段；没有查看或展示reasoning_content，没有干预driver。

10:19:20.823105 UTC，fresh_verification.source_recheck已ACCEPTED，error=null，repair_count=0。该run已有8条新EvidenceRecord；其中4条明确绑定旧卡claim@1并带目标指纹：

| EvidenceRecord | 明确目标 | 关系 / 验证状态 |
|---|---|---|
| ev_bca90eb8a17c9414105920473502a80b | draft.claim.small_scale_inseparability_risk@1 | supports / verified |
| ev_0afb8d3770e8fa8d3f5e47f2045cee48 | draft.claim.small_scale_inseparability_risk@1 | supports / verified |
| ev_0643916ef0fab7730851e3ef88415208 | draft.claim.small_scale_inseparability_risk@1 | supports / verified |
| ev_0a51358869118c2b484a1e2464ddc472 | draft.claim.metric_separability_hypothesis@1 | motivates / verified |

前三条来自PQ批评文，目标指纹为 `8861da4b652d7235240a4f507bee9cbc8cca39bbc9d839e7aad4b951ecfd6d8d`；第四条来自Boundary IoU，目标指纹为 `490dc7d72e350f647d9cc8be23171ab02ac5bb8b3d033fd92d82219df79f6b1d`。其余4条为背景观察，其中2条inference类为unverified。这里已有真实“来源→新EvidenceRecord→具体旧claim/version”绑定，不再沿用10:09时点的零EvidenceRecord计数；issue表仍为空，不能声称解决了empirical issue。

### 首次development回答：JSON提前闭合，多层字段错位

原始最终回答为 `call_b389d76f37bd4f4b811f0c4d38c63bd5`，finish_reason=stop，22045个Unicode字符。运行时记录的首次错误为：`json_invalid: Invalid JSON: trailing characters at line 1 column 46231`。独立JSON检查定位为第21684个Unicode字符开始的额外数据；其前缀恰为46230个UTF-8字节，所以两个位置是一处错误，不是两个不同失败。

模型提前关闭了顶层对象，随后还输出evidence_requests/capability_requests/note。即使只为诊断解析提前闭合的首对象，仍有多层错位：direction_change、affected_claims等DeveloperResult字段被放在外层；method/risks/claims等CardDraft字段被放在result层；distinct_predictions/favored_only_if_justified被移出hypotheses。这个诊断只说明原稿还有什么问题，没有截断原稿来接受它，也没有自动补写字段。

冻结prompt的系统文本明确要求最终只返回一个JSON对象；其Required JSON schema明确给出Envelope的8个必填字段和additionalProperties=false，DeveloperResult、CardDraft、Hypotheses也分别有必填列表及additionalProperties=false。因此首次JSON尾部与字段嵌套错误属于已公开契约，不是未提供schema。原稿保持不变，运行方只允许一次格式修复。

### 修复后的最终停点：多报未改变claim，而非漏报改变或删除

10:21:20.758550 UTC读取的最终run为PAUSED_PROTOCOL / AFFECTED_CLAIMS_COVERAGE、assessment=null，卡仍为 `card_efc859b4332444d48af5362d8b1a208a` v1。development task经一次格式修复后已ACCEPTED，但跨卡版本校验阻止保存新卡；task接受与run完成是两件事。

逐字段比较冻结original_card与proposed_revision，旧/新都为4个claims，无新增、无删除。实际发生变化的集合只有：

- draft.claim.metric_separability_hypothesis：version 1→2、conditions及evidence_ids变化。
- draft.claim.small_scale_inseparability_risk：version 1→2、evidence_ids变化。

模型的affected_claims却列了全部4个，多出了完全未改动的draft.claim.definition_of_error_types和draft.claim.measurement_vs_intervention。没有漏报任何changed/deleted claim，四条evidence_review也都存在。模型在review中明确把前两条新证据用于动机/机制前提，仍将完整可辨识性假说保留为待实验；这证明证据进入了修订候选，但候选未保存，不能记为正式卡v2或科学结论已更新。

`src/arc/validation.py:100` 的validate_revision以完整Claim对象不相等计算changed，并在第108行要求set(affected_claims)==changed；它因此拒绝多列的两个未变化ID。该实现的错误触发可以复现，但本任务冻结的广告schema中affected_claims仅为字符串数组（title=Affected Claims），没有description；冻结roles/developer.md只要求返回affected_claims并指出需重新核查的映射，没有明确“恰等于完整Claim对象差集、禁止多列未改变ID”。所以不能把这一次覆盖错误归因于模型遗漏changed/deleted，也不能说exact-set规则已完整广告。它暴露了跨记录校验比当次可见说明更严格的契约缺口；本审计不修改schema、prompt、原稿或运行结果。

### 此次新增原件hash

路径继续相对于前述artifacts根目录。

| 对象 | 原件路径 | SHA256 |
|---|---|---|
| source_recheck接受原件 | runs/arc-vnext-validation-20260907.explicit_input_schema_v2.develop/tasks/dec78a8b45529feb355559e19ca0db7f471fca71a5d3fff4911b77e7f53db471/states/73c10abafe4b4b7a83587d2f7fe58174.json | 5911f7aad1739b44a53294eb9570e1b07698389506d8d0f3803877637f60a96d |
| development初始最终回答 | runs/arc-vnext-validation-20260907.explicit_input_schema_v2.develop/tasks/f62da399e7f9aa1b4c87317b48993c5eb53bf96a67d6ae3418e5e9f91a8ef933/states/f4d3d832f88442e5bf0b9e7b709cdcf6.json | 4ca23e5989ae53323abb3d55d7415a3cb88994ca3f6ccf474e9f4132668fb500 |
| development冻结prompt | runs/arc-vnext-validation-20260907.explicit_input_schema_v2.develop/tasks/f62da399e7f9aa1b4c87317b48993c5eb53bf96a67d6ae3418e5e9f91a8ef933/prompt.json | f5b7bccdc25072b91e427516e67027d549812301687a47edfa8e74ed502718ea |
| development修复后的回答 | runs/arc-vnext-validation-20260907.explicit_input_schema_v2.develop/tasks/f62da399e7f9aa1b4c87317b48993c5eb53bf96a67d6ae3418e5e9f91a8ef933/states/08c734fc306c4ac39396acfdb9f42aad.json | 6eebef9c7c5d0d561134230b0663204221033ca8b04ad29d5381440b813b096e |

初始最终回答content单独SHA256：`d63ee13884ffa0ba81566c4a7ccf3b6b21fa98b53f68d6fd0e319393d4621904`；修复回答 `call_b1da8ceab2b74c168e480a78e159656f` 的content SHA256：`856a6ac6cefc5eefa955d6b34e7ebff45446329d5153e04ceb71a4d329658843`。冻结Required JSON schema按sort_keys=true、ensure_ascii=false、separators=(',',':')序列化后的SHA256为 `4886e4da6343e9776cb0d3541c642fe47ea8ae04ea8599b17e01b28112e17527`；该hash是schema对象的审计hash，不冒充整个prompt文件hash。
