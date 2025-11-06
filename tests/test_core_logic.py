# region Smoke test for core_logic.py
# INPUT: None
# OUTPUT: None (asserts import)
def test_import_core_logic():
    # Remove sys.path manipulation
    # Import using the full package path, assuming conftest.py handles the root path
    from autotype_mcp_server.src import core_logic 
    assert core_logic is not None
# endregion 