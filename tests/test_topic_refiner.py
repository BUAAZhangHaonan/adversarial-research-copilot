from arc.topic_refiner import build_topic_refine_report, extract_refined_topic


def test_extract_refined_topic_from_heading() -> None:
    text = """
# 优化题面

基于小波多尺度特征与大模型流形学习的跨域异常检测框架。

## 研究假设
...
"""
    out = extract_refined_topic(text)
    assert "小波多尺度特征" in out


def test_extract_refined_topic_fallback_first_line() -> None:
    text = "最终题目：面向工业振动信号的小波-流形联合表征。"
    out = extract_refined_topic(text)
    assert out.startswith("最终题目")


def test_build_topic_refine_report_contains_sections() -> None:
    report = build_topic_refine_report(
        original="原题",
        refined="优化题",
        rounds=[],
    )
    assert "# Topic Refinement Report" in report
    assert "## Original Topic" in report
    assert "优化题" in report
