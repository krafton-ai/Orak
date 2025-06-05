import json
import time
import os
import re
from abc import ABC, abstractmethod


import time
from abc import ABC, abstractmethod


class SafeFileLoader(ABC):
    def __init__(self, file_path, default_output, max_retries=5, delay=0.1):
        if not (file_path.endswith('.txt') or file_path.endswith('.json')):
            raise ValueError()
        self.file_path = file_path
        self.max_retries = max_retries
        self.delay = delay
        self.default_output = default_output

        try:
            self.last_update = os.path.getmtime(self.file_path)
        except FileNotFoundError:
            self.last_update = None

    def get_file_path(self):
        return self.file_path

    @abstractmethod
    def process_content(self):
        pass

    def load(self, wait_for_update=False, and_delete=False):
        if wait_for_update:
            start_time = time.time()
            while True:
                try:
                    current_mod_time = os.path.getmtime(self.file_path)
                except FileNotFoundError:
                    current_mod_time = None

                if self.last_update is None:
                    self.last_update = current_mod_time
                    break

                if current_mod_time != self.last_update:
                    self.last_update = current_mod_time
                    break

                if time.time() - start_time > 3:
                    print("3초 경과, 업데이트가 없으므로 로드를 진행합니다.")
                    break

                time.sleep(self.delay)

        result = None
        if self.max_retries == 'inf':
            while True:
                try:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        self.file_obj = f
                        result = self.process_content()
                    break
                except FileNotFoundError:
                    time.sleep(self.delay)
        else:
            for attempt in range(1, self.max_retries + 1):
                try:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        self.file_obj = f
                        result = self.process_content()
                    break
                except FileNotFoundError:
                    if attempt == self.max_retries:
                        result = self.default_output
                        break
                    time.sleep(self.delay)

        self.file_obj = None

        if and_delete and os.path.exists(self.file_path):
            while True:
                try:
                    os.remove(self.file_path)
                    break
                except:
                    continue

        return result

    def exists(self):
        return os.path.exists(self.file_path)

    def remove(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


class ActiveKeyTypeLoader(SafeFileLoader):
    def process_content(self):
        content = self.file_obj.read().strip()
        return [s.strip() for s in content.split(',') if s.strip()]


class CurrentSavepageIndexLoader(SafeFileLoader):
    def process_content(self):
        return int(self.file_obj.read().strip())


class ConfirmInitialCursorLoader(SafeFileLoader):
    def process_content(self):
        return str(self.file_obj.read().strip())


class OptionCursorLoader(SafeFileLoader):
    def process_content(self):
        return str(self.file_obj.read().strip())


class ConversationLogLoader(SafeFileLoader):
    def process_content(self):
        content = self.file_obj.read().strip().strip("|").replace("\n", " ")
        content = re.sub(r"\|+", ",", content)
        data_list = eval(f"[{content}]")
        return data_list


class MultiChoiceLoader(SafeFileLoader):
    def process_content(self):
        return json.load(self.file_obj)


class RecordEvidenceLogLoader(SafeFileLoader):
    def process_content(self):
        content = self.file_obj.read().strip()
        record_json = eval(f"{content}")
        timestamp = record_json["timestamp"]
        data_list = record_json["data"]
        result = {}
        for entry in data_list:
            key = entry.get("id")
            result[key] = {"name": entry.get(
                "name"), "desc": entry.get("desc")}
        return (result, timestamp)


class RecordProfileLogLoader(SafeFileLoader):
    def process_content(self):
        content = self.file_obj.read().strip()
        record_json = eval(f"{content}")
        timestamp = record_json["timestamp"]
        data_list = record_json["data"]
        result = {}
        for entry in data_list:
            key = entry.get("id")
            result[key] = {"name": entry.get(
                "name"), "desc": entry.get("desc")}
        return (result, timestamp)


class FlagChecker:
    def __init__(self, file_path):
        self.file_path = file_path

    def exists(self):
        return os.path.exists(self.file_path)

    def remove(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


class AutoInputFileCreator:
    def __init__(self, file_path):
        self.file_path = file_path

    def create_file(self, input_str):
        with open(self.file_path, "w") as f:
            f.write(input_str.strip() + "\n")
