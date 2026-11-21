# 从研究工作台提交选定的问题

外部调用方先固定选中的方向快照、画像、具体研究问题和已读材料，再请求一个轻量预研阶段。`develop` 展开研究方案，`run` 核对关键前提。每次提交只执行所选阶段。ARC 为导入的想法分配自己的 `idea_id`，它与外部方向 ID 分开保存。

## 调用顺序

将 ARC 可执行文件和参数数组交给进程 API，使用同一套运行配置、服务环境与私有数据目录。

```bash
arc --config /path/to/runtime.yaml --env-file /path/to/arc.env --data-dir /path/to/arc-data handoff import < selected.json
arc --config /path/to/runtime.yaml --env-file /path/to/arc.env --data-dir /path/to/arc-data handoff execute HANDOFF_ID
arc --config /path/to/runtime.yaml --env-file /path/to/arc.env --data-dir /path/to/arc-data handoff result HANDOFF_ID
```

`import` 只登记材料、阶段及其预算账户，返回真实的想法和运行标识。`execute` 调用常规的轻量阶段、费用账本与中文 writer，以服务端配置的正数阶段预算运行。三个命令的成功结果均是 stdout 上的单个 JSON，执行进度进入 stderr。`result` 读取同一任务，通信中断时可先按原 `handoff_id` 查询。再次执行同一请求会继续同一运行；另一个进程正在执行时直接返回其状态。

初次提交省略顶层 `idea_id`。在同一想法上进入下一阶段时，使用新的 `handoff_id`、上次返回的 `idea_id` 和选定的阶段。ARC 将已经完成的最新预研笔记、保存的资料与这次的新增输入一起冻结。原有快照未被改写。一个方向上的另一个切口使用独立提交且省略 `idea_id`。已登记的 `handoff_id` 只能对应相同的冻结输入。

## 输入字段

| 字段 | 内容 |
| --- | --- |
| schema_version | 固定为 `radar.arc.selected-idea.v1` |
| handoff_id、idea_id | 调用方持久请求 ID，以及可选的既有 ARC 想法 ID |
| origin | `system="ScholarRadar"`、`direction_id`、`snapshot_id`、`profile_id` |
| request | `stage`、用户补充的 `focus` 和 `boundaries[]` |
| proposal | `title`、`question`、`hypothesis`、`expected_value`、`claimed_difference`、`decisive_unknown` |
| sources | 各份来源的 `external_source_id`、题名、原始 URL、版本、可选的作品/修订/引文 ID 以及阅读层级 |
| source_notes | 每份笔记的 `external_source_id`、`finding`、`relevance`、`access`，可补充 `limits` |
| profile、assets、resource_conditions | 冻结画像对象、可复用资产数组、资源条件对象 |

每个 source 表示一个可核对的版本与连续文本。原文字段是 `content`，`start_char` 为 Unicode 起始字符，`total_chars` 为该文本模式的总字符数。对于 `full_text`，两者必须证明全文从字符 0 起且覆盖全部。多个不相连的引文需要分开登记。`passage`、`abstract`、`code`、`secondary` 保留相应材料；`metadata` 只登记书目信息。代码来源可指定 `source_type="author_code"`。ARC 返回实际注册的来源 ID 与外部映射，科学笔记使用原文的真实 ARC ID。

## 读取结果

`radar.arc.prestudy.v1` 同时返回阶段执行状态、研究决策和成文状态。`execution_status` 可为 `prepared`、`running`、`completed`，或实际的暂停、取消和错误状态。`research_decision`、`current_understanding`、`next_question` 来自这次轻量预研的笔记。`evidence_limited` 表示材料获取限制。没有产生决策时相应字段为空。阶段正常结束也可以得到“只作线索”或“暂不推进”的研究判断。

`presentation` 直接包含 ARC writer 的 `stage_summary`、`overview`、`candidates[].text` 和 `technical_analysis`。若成文未通过而研究已完成，`presentation_status="draft"`，`draft` 为保存的研究笔记，`draft_text` 提供可读原稿。调用方可以直接展示，不需再次触发研究或压缩中文正文。

`cited_source_ids` 与 `source_directory` 一起使用。每个来源有题名、URL、版本、阅读层级和已记录的笔记，目录也包含本阶段补查的新来源。`source_mapping` 保留外部的作品、修订与引文定位。`cost` 是当前 ARC 运行实际账本，缺失计费信息沿用账本的未知状态。
