# read_paper

读取论文原文，不代替你的研究判断。query 接受确认的 arXiv ID/URL、DOI 或论文页面 URL；已有 PDF 直链可用 pdf_url。不要把标题、摘要、提问或章节需求拼入标识。网页工具返回 requires_pdf_reader 时，用它给出的 pdf_url 交接。

query、pdf_url、document_id 三个入口一次只选一个。document_id 必须来自本工具返回，不能填 ARC 的 src_... 来源编号；已有 src_... 应交给 read_record。合法示例：query="2412.14672"；pdf_url="https://aclanthology.org/2024.findings-acl.212.pdf"。不要把 arXiv 前缀、论文名或说明拼到纯编号后面。

首读默认最多 64000 字符。后续优先用 document_id 和 next_offset 读取同一缓存版本，或用 find_text 定位关键词；无需重新下载。只读解决当前问题需要的段落，完成后停止翻页。eof 只表示该页到达末尾，不能证明先前全部内容已经读过。coverage、content_complete 和 content_start_char 标明实际覆盖；引用 chars/lines 定位以 ARC 缓存正文为坐标，片段的原文偏移单独保留。

核对原文的具体主张、设置和限制。元数据、自动分析和未经查阅的图表不能充当已核实原文。访问失败就保留该项不确定性，继续其他可做判断，不补写未读内容。

论文内查词省略 limit_chars 时，命中只返回约 4000 字符；普通读取缺省最多 64000 字符。未命中返回 no_match，不返回或登记正文；这只表示该范围没有这个字符串，不能据此断言论文没有讨论该概念。
