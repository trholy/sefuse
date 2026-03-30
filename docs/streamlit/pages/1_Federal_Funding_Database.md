# `streamlit.pages.1_Federal_Funding_Database` 
 
Entry-point module for the German funding search page in Streamlit. 
 
## Behavior 
 
- Initializes the authentication system before the page is rendered. 
- Stops the page with an error message when authentication startup fails. 
- Requires an authenticated session when authentication is enabled. 
- Imports `GermanFundingSearchPage` from the UI layer. 
- Instantiates the page class and immediately calls `.render()`. 
- Renders the shared logout control after the page content.
