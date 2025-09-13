import json
import threading
from pathlib import Path


class PersistentDict:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, json_path="local_db.json"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_instance(json_path)
        return cls._instance

    def _init_instance(self, json_path):
        base_path = Path(__file__).parent
        self._file_path = base_path / json_path
        self._data = self._load_from_file()

    def _load_from_file(self):
        if self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as file:
                    return json.load(file)
            except json.JSONDecodeError:
                return {}  # Return empty dict if file is corrupted
        return {}

    def _save_to_file(self):
        with open(self._file_path, "w", encoding="utf-8") as file:
            json.dump(self._data, file, indent=4, default=str)

    def __getitem__(self, key):
        return self._data.get(key)

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        if key in self._data:
            del self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def clear(self):
        self._data.clear()

    def update(self, *args, **kwargs):
        self._data.update(*args, **kwargs)

    def save(self):
        self._save_to_file()

    def __contains__(self, key):
        return key in self._data

    def __repr__(self):
        return f"PersistentDict({self._data})"


store = PersistentDict()
