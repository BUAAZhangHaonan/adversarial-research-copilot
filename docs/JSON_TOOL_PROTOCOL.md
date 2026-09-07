# JSON与原生工具协议验证

V3的共享调查、COMPOSE及novelty在原生工具循环后多次返回非JSON，消耗一次结构修复。novelty修复后又因请求归属无效而暂停；JSON语法与角色语义契约是两个独立检查。

代码原先在存在tools时省略response_format，只有无tools时才启用json_object。附近禁止tool_choice的注释不构成禁用JSON模式的依据。

2026-09-07只读核查：[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)同一请求列出thinking、reasoning_effort、tools、response_format；[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)说明思考模式支持工具；[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)以默认开启思考的v4-pro示例JSON模式。未发现这些字段互斥的官方要求，但文档没有提供全部字段组合的完整示例，文档本身不等于服务端联合验证。

修复统一发送response_format=json_object，保持全部语义请求thinking enabled、effort=max、max_tokens=384000、stream及native tools；不发送tool_choice、不改变预算或重试。JSON模式仍不保证schema/引用/科研判断正确，空正文和非JSON仍按原单次repair与失败暂停处理。

离线使用实际OpenAI SDK 2.54.0及httpx.MockTransport核对Flash/Pro连续两次native工具调用和最终JSON的完整请求体、reasoning/tool_call_id历史及恢复零重复调用；另覆盖空正文/纯文字与修复成功/失败组合。该测试不连接真实API。

真实联合probe使用唯一父账本arc-vnext-validation-20260907下protocol_json_tools.MODEL子账户，保持每阶段20元和总100元上限。它要求读取当前run元数据一次再完成FRAME，不把元数据当科研证据。逐调用请求、真实工具trace、repair_count与finish_reason写入该run的joint-protocol-audit.json；结果见最终E2E_REPORT及COST_REPORT。两个模型的实际联合结果尚待本轮运行，不能提前声称验证通过。
