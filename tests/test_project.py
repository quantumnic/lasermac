"""Tests for project save/load."""


from lasermac.project import Project, add_recent_file, load_recent_files


class TestProject:
    def test_empty_project(self):
        p = Project()
        assert p.version == 1
        assert p.shapes == []
        assert p.layers == []

    def test_to_dict_from_dict(self):
        p = Project(
            name="Test Job",
            shapes=[{"kind": "rect", "points": [[0, 0], [100, 100]]}],
            settings={"work_x": 300},
        )
        d = p.to_dict()
        restored = Project.from_dict(d)
        assert restored.name == "Test Job"
        assert len(restored.shapes) == 1
        assert restored.settings["work_x"] == 300

    def test_save_and_load(self, tmp_path):
        p = Project(name="My Project", shapes=[{"kind": "line"}])
        path = str(tmp_path / "test.lmc")
        p.save(path)

        loaded = Project.load(path)
        assert loaded.name == "My Project"
        assert len(loaded.shapes) == 1

    def test_save_adds_extension(self, tmp_path):
        p = Project(name="NoExt")
        path = str(tmp_path / "test_no_ext")
        p.save(path)
        assert (tmp_path / "test_no_ext.lmc").exists()

    def test_load_nonexistent_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            Project.load("/tmp/nonexistent_project_xyz.lmc")


class TestRecentFiles:
    def test_add_and_load(self, tmp_path, monkeypatch):
        rf_path = tmp_path / "recent_files.json"
        monkeypatch.setattr("lasermac.project.recent_files_path", lambda: rf_path)

        add_recent_file("/tmp/file1.lmc")
        add_recent_file("/tmp/file2.lmc")

        recents = load_recent_files()
        assert len(recents) == 2
        assert recents[0].endswith("file2.lmc")  # most recent first

    def test_no_duplicates(self, tmp_path, monkeypatch):
        rf_path = tmp_path / "recent_files.json"
        monkeypatch.setattr("lasermac.project.recent_files_path", lambda: rf_path)

        add_recent_file("/tmp/file1.lmc")
        add_recent_file("/tmp/file2.lmc")
        add_recent_file("/tmp/file1.lmc")  # re-add

        recents = load_recent_files()
        assert len(recents) == 2

    def test_max_count(self, tmp_path, monkeypatch):
        rf_path = tmp_path / "recent_files.json"
        monkeypatch.setattr("lasermac.project.recent_files_path", lambda: rf_path)

        for i in range(15):
            add_recent_file(f"/tmp/file{i}.lmc")

        recents = load_recent_files(max_count=10)
        assert len(recents) == 10

    def test_empty_when_no_file(self, tmp_path, monkeypatch):
        rf_path = tmp_path / "nonexistent_recent.json"
        monkeypatch.setattr("lasermac.project.recent_files_path", lambda: rf_path)
        assert load_recent_files() == []
