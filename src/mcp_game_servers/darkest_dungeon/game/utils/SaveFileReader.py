import os
import time
import subprocess

from pathlib import Path


class SaveFileReader:
    def __init__(self, save_editor_path, save_profile_path, game_install_location):
        # Convert paths to absolute Path objects during initialization
        self.SaveEditorPath = Path(save_editor_path).resolve()
        self.SaveProfilePath = Path(save_profile_path).resolve()
        self.GameInstallLocation = Path(game_install_location).resolve()
    
    def save_editor_path(self):
        return self.SaveEditorPath / "game_states"
    
    def game_install_location(self):
        return self.GameInstallLocation

    def decrypt_save_info(self, file):
        filepath = self.SaveEditorPath / "game_states" / file
        jar_path = self.SaveEditorPath / "DDSaveEditor.jar"
        input_path = self.SaveProfilePath / file

        # Verify jar file exists
        if not jar_path.exists():
            raise FileNotFoundError(f"JAR file not found at: {jar_path}")

        if filepath.exists():
            try:
                filepath.unlink()
            except PermissionError:
                time.sleep(0.2)
                filepath.unlink()

        subprocess.call([
            'java',
            '-jar',
            str(jar_path),  # Convert Path to string
            'decode',
            '-o',
            str(filepath),  # Convert Path to string
            str(input_path)  # Convert Path to string
        ])
        print(f'decrypted {file}!')