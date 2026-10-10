from ui import GermanFundingSearchPage
from auth.handlers import (
    safe_bootstrap,
    render_logout_button,
    require_login,
)

safe_bootstrap()

require_login()
page = GermanFundingSearchPage()
page.render()
render_logout_button()
