import pytest
from analyzer.analysis import parse_analysis, Analysis, AnalysisParseError


def test_parse_clean_json():
    text = '{"label": "impact", "severity": "high", "explanation": "強い衝撃を検知"}'
    a = parse_analysis(text)
    assert a == Analysis(label="impact", severity="high", explanation="強い衝撃を検知")


def test_parse_json_with_surrounding_text():
    text = 'はい、結果です:\n{"label": "tilt", "severity": "low", "explanation": "傾き軽微"} 以上'
    a = parse_analysis(text)
    assert a.label == "tilt"
    assert a.severity == "low"


def test_parse_invalid_label_raises():
    text = '{"label": "explosion", "severity": "high", "explanation": "x"}'
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


def test_parse_invalid_severity_raises():
    text = '{"label": "impact", "severity": "critical", "explanation": "x"}'
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


def test_parse_empty_explanation_raises():
    text = '{"label": "impact", "severity": "high", "explanation": "  "}'
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


def test_parse_no_json_raises():
    with pytest.raises(AnalysisParseError):
        parse_analysis("no json here")
