# region Smoke test for mcp_server.py
# INPUT: None
# OUTPUT: None (asserts import)
def test_import_mcp_server():
    import sys
    sys.path.append('autotype_mcp_server/src')
    import mcp_server
    assert mcp_server is not None
# endregion 