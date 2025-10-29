from pipeline.common import PageText, checksum
from pipeline.validators.counters import compute_metrics


def make_page(num: int, text: str) -> PageText:
    return PageText(page_num=num, raw_text=text, norm_text=text, checksum=checksum(text))


def test_compute_metrics_no_diff():
    pre = [make_page(1, "Hello world"), make_page(2, "Second page")]
    post = [make_page(1, "Hello world"), make_page(2, "Second page")]
    metrics = compute_metrics(pre, post)
    assert metrics["summary"]["flags"] == []
    assert all(not page["flags"] for page in metrics["pages"])


def test_compute_metrics_mismatch():
    pre = [make_page(1, "Hello"), make_page(2, "World")]
    post = [make_page(1, "Hello"), make_page(2, "Different")]
    metrics = compute_metrics(pre, post)
    flagged = [page for page in metrics["pages"] if page["flags"]]
    assert flagged and flagged[0]["flags"][0] == "text_mismatch"
