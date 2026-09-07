# JSON与原生工具协议验证

截至2026-09-07，`0f66f56` 的Flash/Pro联合真实probe均COMPLETED：各两次模型请求、一次真实read_record、repair_count=0，最终finish_reason=stop。这验证了本次JSON与原生工具的组合；V3旧novelty失败仍保留，没有被改成成功。

V3的共享调查、COMPOSE及novelty在原生工具循环后多次返回非JSON，消耗一次结构修复。novelty修复后又因请求归属无效而暂停；JSON语法与角色语义契约是两个独立检查。

代码原先在存在tools时省略response_format，只有无tools时才启用json_object。附近禁止tool_choice的注释不构成禁用JSON模式的依据。

2026-09-07只读核查：[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)同一请求列出thinking、reasoning_effort、tools、response_format；[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)说明思考模式支持工具；[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)以默认开启思考的v4-pro示例JSON模式。未发现这些字段互斥的官方要求，但文档没有提供全部字段组合的完整示例，文档本身不等于服务端联合验证。

修复统一发送response_format=json_object，保持全部语义请求thinking enabled、effort=max、max_tokens=384000、stream及native tools；不发送tool_choice、不改变预算或重试。JSON模式仍不保证schema/引用/科研判断正确，空正文和非JSON仍按原单次repair与失败暂停处理。

离线使用实际OpenAI SDK 2.54.0及httpx.MockTransport核对Flash/Pro连续native工具调用和最终JSON的完整请求体、reasoning/tool_call_id历史及恢复零重复调用；另覆盖空正文/纯文字与修复成功/失败组合。具体测试为 `tests/test_runtime.py` 的 `test_native_tool_reasoning_association_and_trace` 和 `test_native_json_output_invalid_or_empty_keeps_single_repair_policy`，测试本身不连接真实API。0f66f56完整suite为263 passed / 48.55s，远端日志 `work/tests-json-tools.log`；该HEAD独立wheel检查通过，日志 `work/wheel-build-0f66f56.log`、`work/wheel-install-0f66f56.log`、`work/wheel-help-0f66f56.log`。

真实联合probe使用唯一父账户 `arc-vnext-validation-20260907` 下的 `protocol_json_tools.MODEL` 子账户，保持每阶段20元和总100元上限。它要求读取当前run元数据一次再完成FRAME，不把元数据当科研证据。两模型均实际完成，审计的 `all_requests_json_tools_max_full_output=true`，所有模型请求同时保留JSON模式、native tools、thinking/max、384000上限和stream；结束时reserved=0、unknown_calls=0。

| 模型 | 完整run ID | 模型请求ID | 实际read_record tool ID | 费用区间（人民币） |
|---|---|---|---|---:|
| Flash | `arc-vnext-validation-20260907.protocol_json_tools.deepseek-v4-flash` | `call_f3ec7073a49f4a2f893a757ce75e6970`、`call_b451917bcc184e628a38e11f97a1e215` | `tool_0e29f9f6184e479d85e52e53a5b82a88` | 0.019979–0.019981 |
| Pro | `arc-vnext-validation-20260907.protocol_json_tools.deepseek-v4-pro` | `call_eb58225ad1cc48d19b283702da5d840d`、`call_34ce28d3585e46e2be1cebc8e2f221ad` | `tool_9c602b05670c49f1bed582498f77f99f` | 0.077400–0.077402 |

原件保存在隔离目录 `/home/g203/zhanghaonan/arc-vnext-20260907` 的 `.arc-validation/artifacts/runs/<run_id>/joint-protocol-audit.json`；汇总日志为 `work/live-joint-probe.log`。本次只读核对了日志及两份审计文件路径，未为文档重新发请求。两个子账各有三条调用记录，其中两条模型请求、一条本地工具调用；费用区间不是正式发票或父账本总费用。

相邻提交 `2b8b79a` 另冻结comparison.boundaries与shuffle_seed，并追加公共EvidenceRequest归属说明；这不等于执行了L4。V3卡虽已保存，旧novelty仍因一次修复后三个request目标全null而 `INVALID_OUTPUT_AFTER_REPAIR`，子账4.529248–4.539975元，没有accepted novelty或科学裁决。明确标记的 `explicit_input.develop/run` 正在验证L2入口，尚无结果；L3未完成，L4未执行。联合协议成功只关闭这里的参数组合验证，后续科研判断仍须完整schema、原文与目标归属检查，分层结果见 [E2E_REPORT](E2E_REPORT.md)。
