import pytest
from backend.app.api.v1.users import register_user_session, validate_user_session, revoke_user_sessions

def test_single_session_enforcement_invalidates_previous_token():
    username = "admin_test"
    
    # 1. User logs in on PC A -> gets token A
    token_a = register_user_session(username)
    assert token_a is not None
    assert validate_user_session(username, token_a) is True
    
    # 2. User logs in on PC B under the same username -> gets token B
    token_b = register_user_session(username)
    assert token_b is not None
    assert token_b != token_a
    
    # 3. PC A's token MUST be invalidated immediately (kick-out)
    assert validate_user_session(username, token_a) is False, "Previous session token must be invalidated"
    
    # 4. PC B's token remains valid
    assert validate_user_session(username, token_b) is True, "Latest session token must be valid"
    
    # 5. Revoking session invalidates token B as well
    revoke_user_sessions(username)
    assert validate_user_session(username, token_b) is False
