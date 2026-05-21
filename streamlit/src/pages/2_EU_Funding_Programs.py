from ui import EuFundingSearchPage
from auth.handlers import (
    safe_bootstrap,
    render_logout_button,
    require_login,
)

safe_bootstrap()

require_login()
page = EuFundingSearchPage()
page.render()
render_logout_button()
