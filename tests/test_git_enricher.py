import subprocess
from unittest.mock import patch

import pytest

from coderag.enrichment.git_enricher import CoChangeEntry, FileGitMetrics, GitEnricher, GitEnrichmentResult


@pytest.fixture
def mock_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    return str(repo_dir)


def test_init_not_git_repo(tmp_path):
    with pytest.raises(ValueError, match="Not a git repository"):
        GitEnricher(str(tmp_path))


def test_enrich_no_commits(mock_repo):
    enricher = GitEnricher(mock_repo)
    with patch.object(enricher, "_get_commit_history", return_value={}):
        result = enricher.enrich()
        assert result.total_commits_analyzed == 0
        assert len(result.file_metrics) == 0


def test_enrich_exception(mock_repo):
    enricher = GitEnricher(mock_repo)
    with patch.object(enricher, "_get_commit_history", side_effect=RuntimeError("Test error")):
        result = enricher.enrich()
        assert "Test error" in result.errors[0]


def test_enrich_to_dicts(mock_repo):
    enricher = GitEnricher(mock_repo)

    mock_result = GitEnrichmentResult(
        file_metrics={"test.py": FileGitMetrics(file_path="test.py", commit_count=5, is_hot_file=True)},
        co_changes=[
            CoChangeEntry(file_a="test.py", file_b="utils.py", co_change_count=3, confidence=0.6, jaccard_index=0.5)
        ],
        total_commits_analyzed=10,
        total_authors=2,
        analysis_time_ms=100.0,
    )

    with patch.object(enricher, "enrich", return_value=mock_result):
        dicts = enricher.enrich_to_dicts()
        assert "test.py" in dicts["file_metrics"]
        assert dicts["file_metrics"]["test.py"]["commit_count"] == 5
        assert len(dicts["co_changes"]) == 1
        assert dicts["co_changes"][0]["file_a"] == "test.py"
        assert dicts["stats"]["total_commits_analyzed"] == 10


def test_run_git_timeout(mock_repo):
    enricher = GitEnricher(mock_repo)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=120)):
        assert enricher._run_git("log") == ""


def test_run_git_file_not_found(mock_repo):
    enricher = GitEnricher(mock_repo)
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        assert enricher._run_git("log") == ""


def test_get_commit_history_empty_raw(mock_repo):
    enricher = GitEnricher(mock_repo)
    with patch.object(enricher, "_run_git", return_value="   \n  "):
        assert enricher._get_commit_history() == {}


def test_get_commit_history_value_error(mock_repo):
    enricher = GitEnricher(mock_repo)
    raw_log = "COMMIT|hash1|Author|2023-01-01T00:00:00Z\ninvalid\tdeleted\tfile.py\n\n"
    with patch.object(enricher, "_run_git", return_value=raw_log):
        commits = enricher._get_commit_history()
        assert commits["hash1"]["files"][0]["added"] == 0
        assert commits["hash1"]["files"][0]["deleted"] == 0


def test_compute_file_metrics_value_error(mock_repo):
    enricher = GitEnricher(mock_repo)
    commits = {
        "hash1": {
            "hash": "hash1",
            "author": "Author",
            "date": "invalid-date",
            "files": [{"path": "file.py", "added": 10, "deleted": 5}],
        }
    }
    metrics = enricher._compute_file_metrics(commits)
    assert metrics["file.py"].age_days == 0


def test_mark_hot_files_empty(mock_repo):
    enricher = GitEnricher(mock_repo)
    # Should not raise
    enricher._mark_hot_files({})


def test_compute_co_changes_max_files(mock_repo):
    enricher = GitEnricher(mock_repo)
    enricher.MAX_FILES_PER_COMMIT = 2
    commits = {"hash1": {"hash": "hash1", "files": [{"path": "f1.py"}, {"path": "f2.py"}, {"path": "f3.py"}]}}
    metrics = {
        "f1.py": FileGitMetrics(file_path="f1.py", commit_count=1),
        "f2.py": FileGitMetrics(file_path="f2.py", commit_count=1),
        "f3.py": FileGitMetrics(file_path="f3.py", commit_count=1),
    }
    co_changes = enricher._compute_co_changes(commits, metrics)
    assert len(co_changes) == 0


def test_compute_co_changes_low_confidence(mock_repo):
    enricher = GitEnricher(mock_repo)
    enricher.MIN_CO_CHANGE_COUNT = 1
    enricher.MIN_CO_CHANGE_CONFIDENCE = 0.9

    commits = {
        "hash1": {"hash": "hash1", "files": [{"path": "f1.py"}, {"path": "f2.py"}]},
    }
    metrics = {
        "f1.py": FileGitMetrics(file_path="f1.py", commit_count=10),
        "f2.py": FileGitMetrics(file_path="f2.py", commit_count=10),
    }
    co_changes = enricher._compute_co_changes(commits, metrics)
    assert len(co_changes) == 0


def test_compute_co_changes_jaccard(mock_repo):
    enricher = GitEnricher(mock_repo)
    enricher.MIN_CO_CHANGE_COUNT = 1
    enricher.MIN_CO_CHANGE_CONFIDENCE = 0.1

    commits = {
        "hash1": {"hash": "hash1", "files": [{"path": "f1.py"}, {"path": "f2.py"}]},
        "hash2": {"hash": "hash2", "files": [{"path": "f1.py"}]},
    }
    metrics = {
        "f1.py": FileGitMetrics(file_path="f1.py", commit_count=2),
        "f2.py": FileGitMetrics(file_path="f2.py", commit_count=1),
    }
    co_changes = enricher._compute_co_changes(commits, metrics)
    assert len(co_changes) == 1
    assert co_changes[0].jaccard_index == 0.5  # intersection(1) / union(2)


def test_full_enrichment_and_dicts(mock_repo):
    # Test with file filter to cover lines 232-235
    enricher = GitEnricher(mock_repo, file_filter={"file1.py", "file2.py"})
    enricher.MIN_CO_CHANGE_COUNT = 1
    enricher.MIN_CO_CHANGE_CONFIDENCE = 0.1

    raw_log = """COMMIT|hash1|Author A|2023-01-01T10:00:00Z
10\t5\tfile1.py
20\t0\tfile2.py
0\t0\tignored.py

COMMIT|hash2|Author B|2023-01-02T10:00:00Z
5\t5\tfile1.py
10\t10\tfile2.py

COMMIT|hash3|Author A|2023-01-03T10:00:00Z
2\t2\tfile1.py
"""
    with patch.object(enricher, "_run_git", return_value=raw_log):
        result = enricher.enrich()
        assert result.total_commits_analyzed == 3
        assert "file1.py" in result.file_metrics
        assert "file2.py" in result.file_metrics
        assert "ignored.py" not in result.file_metrics

        # Cover enrich_to_dicts fully
        dicts = enricher.enrich_to_dicts()
        assert "file1.py" in dicts["file_metrics"]
        assert "file2.py" in dicts["file_metrics"]
        assert len(dicts["co_changes"]) > 0
        assert dicts["stats"]["total_commits_analyzed"] == 3


def test_date_parsing_exception(mock_repo):
    enricher = GitEnricher(mock_repo)
    raw_log = """COMMIT|hash1|Author A|invalid-date-format
10\t5\tfile1.py
"""
    with patch.object(enricher, "_run_git", return_value=raw_log):
        result = enricher.enrich()
        assert "file1.py" in result.file_metrics
        assert result.file_metrics["file1.py"].age_days == 0


def test_co_change_confidence_filtering(mock_repo):
    enricher = GitEnricher(mock_repo)
    enricher.MIN_CO_CHANGE_COUNT = 1
    enricher.MIN_CO_CHANGE_CONFIDENCE = 0.99  # High confidence to filter out

    raw_log = """COMMIT|hash1|Author A|2023-01-01T10:00:00Z
10\t5\tfile1.py
20\t0\tfile2.py

COMMIT|hash2|Author B|2023-01-02T10:00:00Z
5\t5\tfile1.py
"""
    with patch.object(enricher, "_run_git", return_value=raw_log):
        result = enricher.enrich()
        # file1 has 2 commits, file2 has 1 commit. Co-change is 1.
        # min_commits = 1. confidence = 1 / 1 = 1.0. 1.0 > 0.99, so it will be included.
        assert len(result.co_changes) == 1


def test_co_change_confidence_low(mock_repo):
    enricher = GitEnricher(mock_repo)
    enricher.MIN_CO_CHANGE_COUNT = 1
    enricher.MIN_CO_CHANGE_CONFIDENCE = 0.6

    raw_log = """COMMIT|hash1|Author A|2023-01-01T10:00:00Z
10\t5\tfile1.py
20\t0\tfile2.py

COMMIT|hash2|Author B|2023-01-02T10:00:00Z
5\t5\tfile1.py

COMMIT|hash3|Author B|2023-01-03T10:00:00Z
5\t5\tfile2.py
"""
    with patch.object(enricher, "_run_git", return_value=raw_log):
        result = enricher.enrich()
        # file1: 2 commits, file2: 2 commits. Co-change: 1.
        # confidence = 1 / 2 = 0.5. 0.5 < 0.6, so it should be filtered out.
        assert len(result.co_changes) == 0
