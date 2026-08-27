import pytest
from pydantic import ValidationError

from quant_home.config import Settings


def test_lan_binding_rejects_placeholder_admin_password():
    with pytest.raises(ValidationError):
        Settings(
            bind_host="0.0.0.0",
            initial_admin_username="admin",
            initial_admin_password="change-this-password",
        )
