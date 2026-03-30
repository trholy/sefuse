# `streamlit.pages.2_EU_Funding_Programs` 
 
Entry-point module for the EU funding search page in Streamlit. 
 
## Behavior 
 
- Initializes the authentication system before the page is rendered. 
- Stops the page with an error message when authentication startup fails. 
- Requires an authenticated session when authentication is enabled. 
- Imports `EuFundingSearchPage` from the UI layer. 
- Instantiates the page class and immediately calls `.render()`. 
- Renders the shared logout control after the page content.
