import unittest
from kogniterm.terminal.tui.components.status_footer import KogniTermSuggester

class TestKogniTermSuggesterSearch(unittest.TestCase):
    def test_search_files(self):
        suggester = KogniTermSuggester()
        suggester.cached_files_list = [
            "kogniterm/main.py",
            "kogniterm-desktop/main.py",
            "README.md",
            "src/components/button/button.tsx",
            "src/containers/button/button.tsx",
            "kogniterm/core/session_manager.py"
        ]
        
        # Test exact match of filename without extension (ranked high)
        matches = suggester.search_files("main")
        # Ordinal equality but sorted alphabetically in tie
        self.assertEqual(matches[:2], ["kogniterm-desktop/main.py", "kogniterm/main.py"])
        
        # Test case-insensitivity
        matches_caps = suggester.search_files("MAIN")
        self.assertEqual(matches_caps[:2], ["kogniterm-desktop/main.py", "kogniterm/main.py"])
        
        # Test extension matching
        matches_ext = suggester.search_files("main.py")
        self.assertEqual(matches_ext[:2], ["kogniterm-desktop/main.py", "kogniterm/main.py"])
        
        # Test AND matching with multiple terms
        matches_multi = suggester.search_files("core session")
        self.assertEqual(matches_multi, ["kogniterm/core/session_manager.py"])
        
        # Test substring matching on path
        matches_path = suggester.search_files("components button")
        self.assertEqual(matches_path, ["src/components/button/button.tsx"])

    def test_search_files_empty_query(self):
        suggester = KogniTermSuggester()
        suggester.cached_files_list = [
            "a.py",
            "b.py",
            "c.py"
        ]
        # An empty search term should return the top cached files
        matches = suggester.search_files("")
        self.assertEqual(matches, ["a.py", "b.py", "c.py"])

    def test_workspace_directory_none_by_default(self):
        # The suggester should allow workspace_directory to be None initially,
        # so it can be updated on mount from the TUI App.
        suggester = KogniTermSuggester()
        self.assertIsNone(suggester.workspace_directory)

if __name__ == "__main__":
    unittest.main()

