from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from ml.training.fight.prepare_fight_dataset import find_class_dirs  # noqa: E402


def test_fight_prepare_finds_nested_dataset_aliases(tmp_path):
    raw = tmp_path / "raw"
    (raw / "Real Life Violence Dataset" / "Violence").mkdir(parents=True)
    (raw / "Real Life Violence Dataset" / "NonViolence").mkdir(parents=True)
    (raw / "hockey" / "fight").mkdir(parents=True)
    violence = find_class_dirs(raw, ["violence", "fight"])
    non_violence = find_class_dirs(raw, ["non_violence", "nonviolence", "normal"])
    assert raw / "Real Life Violence Dataset" / "Violence" in violence
    assert raw / "hockey" / "fight" in violence
    assert raw / "Real Life Violence Dataset" / "NonViolence" in non_violence
