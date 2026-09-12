# 本轮最终收尾

> 2026-09-12 更新：下面“原地保留”的记录描述当时状态。旧目录现已归并并删除，当前位置见 [档案归并记录](ARCHIVE_CONSOLIDATION_20260912.md)。


2026-09-09。任务书要求的实现、真实运行、两轮对照和软件交付已完成；**自主科学质量目标尚未达到**，不把流程完成或自动偏好写成科研质量通过。逐条对应见[功能重构](FUNCTIONAL_REDESIGN.md)，实际科学结果见[验收结果](FUNCTIONAL_VALIDATION_RESULTS.md)及[两轮对照](FUNCTIONAL_ABLATION_RESULTS.md)。

- 默认链已改为Pro连贯构思、独立科学审查、必要的定向修订与复核；原题贯穿，最多五次，允许零推荐。develop/run显式进入，不执行研究实验、训练或论文写作。
- 四组八个已知语义对照完成目标验收；自然及旧卡最终2＋4项已知问题实修。五张无科学反馈自然卡均未通过独立审阅。两轮D/E有真实局部改善；第一轮仍误放，第二轮E保存v2但自身复核仍要求修订，新的错误尚未消除。
- 两轮A–E共40次模型调用全部结算。r1正序无偏好、交换序偏E；r2正序偏E、交换序偏C，均不足以证明方案总体优胜。B的协议暂停、原接受结果和显式恢复均保留。
- 软件快照55a134c：707通过，0失败/错误/跳过；sdist→wheel、仓库外隔离安装、38提示词/18任务/3配置、4个CLI与依赖检查通过。三项运行期修复分别提交为11d95ae、909f235、05cf26e；55a134c更新旧测试的诊断断言，未删测试。后续提交只更新文档。
- 本轮功能重构新增费用上界95.066385元。历史父账本累计179.876602–180.026722元，预留0、未知0，授权账本余额105.535662元；这不是在线钱包查询。所有失败和重试均计费，不重置历史。[费用明细](COST_REPORT.md)。

## 实际清理结果

最后一批已删除166个明确的旧源码、环境、缓存、过期包及一次性脚本条目，另删除本轮三个已确认归属的pytest临时目录，共169项。此前分批清理仍保留各自记录，不重复计数。

旧detached工作树的源码清理后，小型Git注册文件先归档，再仅移除旧.git文件；prune预览只命中旧登记后才执行。首次预览为中文输出，脚本按保守条件恢复.git，随后固定locale重新预览并完成，未绕过范围检查。最终Git只登记 `/home/g203/zhanghaonan/adversarial-research-copilot` 的master，远程也仅有master分支。

`/home/g203/zhanghaonan/arc-vnext-20260907` 仅保留原地私有数据和历史证据，已加入ARCHIVE_README.md。`.arc-validation`目录与数据库的设备/inode、表计数及运行/账本状态前后不变；没有移动数据库，没有文件哈希校验。最终软件包、付费原件、历史报告、全部成功/失败验证日志继续保留。隔离安装目录在验证及Windows交付完成后删除，不是当前服务依赖。

实际记录位于canonical的：

- `work/cleanup-final-20260908T211655150567Z.json`：166项实际删除与保留核对。
- `work/cleanup-final-pytest-20260908T211613Z.json`：三个pytest目录、归属及原数据不变。
- `work/OLD_WORKTREE_REGISTRATION_ARCHIVE/registration.json`：归档、恢复、预览及最终prune。
- `work/FINAL_PACKAGE_DELIVERY_RECEIPT.json`：最终55软件包与JSON的真实Windows交付回执。

## 尚保留的Windows旧副本

此前自动审批拒绝了以下五项删除，因此未重试或绕过，不能宣称本地旧副本全部清除：

- `E:\OneDrive\文档\Playground\work\arc-vnext`
- `E:\OneDrive\文档\Playground\work\arc-vnext-source.tar`
- `C:\Users\zhn19\Documents\Codex\2026-09-06\new-chat\outputs\delivery-6a350bc`
- `E:\OneDrive\文档\Playground\work\arc-functional`
- `E:\OneDrive\文档\Playground\work\arc-report-redesign`

正式服务中，Agent可以提出能力需求，由用户评估和实现；CodeX只参与本轮开发审阅。后续应关注关键推论的复核与新主题的人类判断，不以增加角色、继续消耗预算或自动评分替代科学质量证据。
